"""FastHTML routes and sessions; presentation lives in templates/ and static/."""
import os
import secrets
import time
from pathlib import Path
from threading import RLock
from urllib.parse import urlencode

from fasthtml.common import FastHTML
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from starlette.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from db import engine, rows
import operations as op

BASE_DIR = Path(__file__).resolve().parent
templates = Environment(
    loader=FileSystemLoader(BASE_DIR / 'templates'),
    autoescape=select_autoescape(['html']),
    undefined=StrictUndefined,
)
app=FastHTML(secret_key=os.getenv('SESSION_SECRET') or secrets.token_hex(32), default_hdrs=False,
    sess_https_only=os.getenv('COOKIE_SECURE')=='1')
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
sessions={}
session_lock=RLock()
SESSION_SECONDS=8*3600


def render(template, *, title, s=None, message='', status_code=200, **context):
    html = templates.get_template(template).render(title=title, s=s, message=message, **context)
    return HTMLResponse(html, status_code=status_code)


def state(session):
    with session_lock:
        now=time.time()
        for key in list(sessions):
            if sessions[key]['expires']<now:
                del sessions[key]
        sid=session.get('sid')
        if sid not in sessions:
            sid=secrets.token_urlsafe(32)
            session.clear(); session['sid']=sid
            sessions[sid]=dict(csrf=secrets.token_hex(32),auth=None,cart={},store=None,token=secrets.token_hex(32),expires=now+SESSION_SECONDS)
        return sessions[sid]


def actor(s):
    with engine.connect() as c:
        return op.identity(c,s['auth'])


def stores(c):
    return [(r['store_id'],r['name']) for r in rows(c,'SELECT * FROM Store ORDER BY store_id')]


@app.get('/')
def home(session, message:str=''):
    s=state(session)
    if s['auth']:
        a=actor(s)
        return render('menu.html', title='Customer menu' if a['kind']=='Customer' else 'Store menu',
                      s=s, a=a, message=message)
    return render('login.html', title='Sign in', s=s, message=message)


@app.get('/register')
def register_page(session, message:str=''):
    s=state(session)
    if s['auth']:
        return RedirectResponse('/',303)
    with engine.connect() as c:
        branches=stores(c)
    return render('register.html', title='Create account', s=s, branches=branches, message=message)


@app.get('/catalog')
def catalog_page(session,store_id:int=0,q:str='',make:str='',model:str='',year:str='',message:str=''):
    s=state(session); a=actor(s)
    with engine.connect() as c:
        branches=stores(c)
        store=store_id or (a.get('pref_store_id') if a['kind']=='Customer' else a['store_id']) or branches[0][0]
        parts=op.catalog(c,store,q,make,model,year)
    return render('catalog.html', title='Parts catalog', s=s, a=a, branches=branches,
                  store=store, parts=parts, q=q, make=make, model=model, year=year, message=message)


@app.get('/cart')
def cart_page(session,message:str=''):
    s=state(session); a=actor(s); op.require(a['kind']=='Customer')
    with engine.connect() as c:
        parts={str(p['part_id']):p for p in rows(c,'SELECT * FROM Part')}
    lines=[dict(part_id=p,name=parts[p]['part_name'],quantity=q,unit_price=parts[p]['price'],subtotal=parts[p]['price']*q) for p,q in s['cart'].items()]
    return render('cart.html', title='Your cart', s=s, a=a, lines=lines,
                  total=sum(r['subtotal'] for r in lines), message=message)


@app.get('/orders')
def orders_page(session,message:str=''):
    s=state(session); a=actor(s)
    with engine.connect() as c:
        cond='customer_id=:id' if a['kind']=='Customer' else 'store_id=:id'
        orders=rows(c,'SELECT * FROM Customer_Orders WHERE '+cond+' ORDER BY customer_order_id DESC',id=a['customer_id'] if a['kind']=='Customer' else a['store_id'])
    return render('orders.html', title='Order history' if a['kind']=='Customer' else 'Branch order queue',
                  s=s, orders=orders, message=message)


@app.get('/orders/{oid}')
def detail_page(oid:int,session,message:str=''):
    s=state(session); a=actor(s); detail=op.order_detail(s['auth'],oid)
    return render('order_detail.html', title=f'Order #{oid}', s=s, a=a, oid=oid,
                  detail=detail, order=detail['order'], message=message)


@app.get('/profile')
def profile_page(session,message:str=''):
    s=state(session); a=actor(s); op.require(a['kind']=='Customer')
    with engine.connect() as c:
        branches=stores(c); vehicles=rows(c,'SELECT * FROM Customer_Vehicle WHERE customer_id=:u',u=a['customer_id'])
    return render('profile.html', title='Profile & vehicles', s=s, a=a, branches=branches,
                  vehicles=vehicles, message=message)


@app.get('/admin')
def admin_page(session,message:str=''):
    s=state(session); a=actor(s); op.require(a['kind']=='Employee')
    with engine.connect() as c:
        roster=rows(c,'SELECT employee_id,name,department,role,username FROM Employee WHERE store_id=:s',s=a['store_id'])
        inventory=op.catalog(c,a['store_id'])
        suppliers=rows(c,'SELECT * FROM Supplier'); links=rows(c,'SELECT * FROM Supplier_Part'); compatibility=rows(c,'SELECT * FROM Part_Compatibility')
    return render('admin.html', title='Store administration', s=s, a=a, roster=roster,
                  inventory=inventory, suppliers=suppliers, links=links, compatibility=compatibility, message=message)


@app.get('/purchases')
def purchases_page(session,message:str=''):
    s=state(session); a=actor(s); op.require(a['kind']=='Employee')
    with engine.connect() as c:
        purchases=rows(c,'SELECT * FROM Store_Orders WHERE store_id=:s ORDER BY store_order_id DESC',s=a['store_id'])
        lines=rows(c,'''SELECT i.* FROM Store_Orders_Item i JOIN Store_Orders o USING(store_order_id) WHERE o.store_id=:s''',s=a['store_id'])
        suppliers=rows(c,'SELECT * FROM Supplier'); links=rows(c,'SELECT * FROM Supplier_Part')
    return render('purchases.html', title='Supplier purchases', s=s, a=a, purchases=purchases,
                  lines=lines, suppliers=suppliers, links=links, message=message)


@app.get('/reports')
def reports_page(session,period:str='daily',scope:str='branch',message:str=''):
    s=state(session); reports=op.reports(s['auth'],period,scope=='all'); a=actor(s)
    return render('reports.html', title='Reports', s=s, a=a, reports=reports,
                  period=period, scope=scope, message=message)


@app.post('/action/{action}')
async def action_page(action:str,request,session):
    f=dict(await request.form())
    return await run_in_threadpool(handle_action,action,session,f)

def handle_action(action,session,f):
    s=state(session)
    op.require(secrets.compare_digest(str(f.get('csrf','')),s['csrf']),'Invalid form token; reload the page')
    destination='/'
    try:
        if action=='login':
            auth=op.login(f.get('kind'),f.get('username'),f.get('password',''))
            with session_lock:
                sessions.pop(session['sid'],None)
                session.clear(); new=state(session); new['auth']=auth
            return RedirectResponse('/',303)
        if action=='register':
            destination='/register'
            op.register(f); return RedirectResponse('/?message=Account+created.+Sign+in.',303)
        if action=='logout':
            with session_lock:
                sessions.pop(session.get('sid'),None); session.clear()
            return RedirectResponse('/',303)
        a=actor(s)
        if action in ('cart_add','cart_clear','checkout'):
            op.require(a['kind']=='Customer')
            destination='/cart'
            with session_lock:
                if action=='cart_clear':
                    s['cart']={}; s['store']=None; s['token']=secrets.token_hex(32)
                elif action=='cart_add':
                    store=op.integer(f.get('store_id')); part=str(op.integer(f.get('part_id'))); qty=op.integer(f.get('quantity'))
                    op.require(not s['cart'] or s['store']==store,'Clear your cart before switching branches')
                    s['store']=store; s['cart'][part]=op.integer(s['cart'].get(part,0)+qty); s['token']=secrets.token_hex(32)
                else:
                    # Successful token remains valid in the database, including a browser retry.
                    token=f.get('token','')
                    if token!=s['token']:
                        with engine.connect() as c:
                            old=rows(c,'SELECT customer_order_id FROM Customer_Orders WHERE customer_id=:u AND submission_token=:t',u=a['customer_id'],t=token)
                        op.require(old,'This checkout form has expired; reload your cart')
                        return RedirectResponse(f"/orders/{old[0]['customer_order_id']}",303)
                    oid=op.checkout(s['auth'],s['store'],dict(s['cart']),token,f)
                    s['cart']={}; s['store']=None; s['token']=secrets.token_hex(32)
                    destination=f'/orders/{oid}'
        elif action in ('order_status','return'):
            oid=op.integer(f.get('order_id')); destination=f'/orders/{oid}'
            if action=='return': op.return_item(s['auth'],oid,f)
            else: op.change_order(s['auth'],oid,f.get('target'))
        elif action in ('purchase','reorder','purchase_status'):
            destination='/purchases'
            if action=='purchase_status': op.change_purchase(s['auth'],f.get('purchase_id'),f.get('target'))
            else: op.purchase(s['auth'],f,f.get('purchase_id') if action=='reorder' else None)
        else:
            destination='/profile' if action in ('profile','vehicle','delete_vehicle') else '/admin'
            op.administer(s['auth'],action,f)
        return RedirectResponse(destination+'?'+urlencode({'message':'Saved successfully.'}),303)
    except (op.RuleError,IntegrityError) as exc:
        message='Record conflicts with existing data or references an invalid ID.' if isinstance(exc,IntegrityError) else str(exc)
        return RedirectResponse(destination+'?'+urlencode({'message':message}),303)


async def rule_error(request,exc):
    return render('error.html', title='Unable to complete request', error=str(exc), status_code=403)


async def database_error(request,exc):
    import logging
    logging.getLogger(__name__).exception('Database operation failed')
    return render('error.html', title='Database unavailable', error='Check database setup and try again. No incomplete transaction was saved.', status_code=503)

app.exception_handlers[op.RuleError]=rule_error
app.exception_handlers[SQLAlchemyError]=database_error

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=int(os.getenv('PORT','5001')))
