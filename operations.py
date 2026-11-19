"""Business operations. Account identity is always reloaded from the database."""
import hashlib
import hmac
import secrets
from datetime import date
from decimal import Decimal, InvalidOperation
from db import engine, run, rows, one

class RuleError(ValueError):
    pass

def require(test, message='Permission denied'):
    if not test:
        raise RuleError(message)

def integer(value, minimum=1, maximum=1000000):
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise RuleError('Enter a whole number')
    require(minimum <= n <= maximum, f'Number must be between {minimum} and {maximum}')
    return n

def money(value):
    try:
        n = Decimal(str(value))
        require(n.is_finite() and 0 <= n <= Decimal('99999999.99'), 'Invalid money amount')
        require(n == n.quantize(Decimal('.01')), 'Use at most two decimal places')
        return n
    except InvalidOperation:
        raise RuleError('Invalid money amount')

def required(value, limit=100):
    value = str(value or '').strip()
    require(0 < len(value) <= limit, f'Enter text up to {limit} characters')
    return value

def password_hash(password):
    require(10 <= len(password) <= 128, 'Password must contain 10–128 characters')
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()
    return f'pbkdf2_sha256${salt}${digest}'

def password_ok(password, stored):
    try:
        algorithm, salt, digest = stored.split('$')
        return algorithm == 'pbkdf2_sha256' and hmac.compare_digest(digest, hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex())
    except (ValueError, AttributeError):
        return False

def identity(conn, auth, employee=False, manager=False):
    require(auth and auth.get('kind') in ('Customer','Employee'))
    table = auth['kind']
    actor = one(conn, f'SELECT * FROM {table} WHERE {table.lower()}_id=:id', id=auth['id'])
    require(actor is not None, 'Account no longer exists; sign in again')
    actor = dict(actor, kind=table)
    require(not employee or table == 'Employee')
    require(not manager or (table == 'Employee' and actor['role'] == 'Manager'))
    return actor

def login(kind, username, password):
    require(kind in ('Customer','Employee'), 'Choose an account type')
    with engine.connect() as c:
        a = one(c, f'SELECT * FROM {kind} WHERE username=:u', u=username)
        require(a and password_ok(password, a['password_hash']), 'Invalid username or password')
        return {'kind':kind, 'id':a[f'{kind.lower()}_id']}

def register(f):
    with engine.begin() as c:
        run(c, '''INSERT INTO Customer(name,address,email,phone,username,password_hash,pref_store_id,pref_payment_method)
        VALUES(:name,:address,:email,:phone,:username,:password_hash,:store,:method)''',
        name=required(f.get('name')), address=required(f.get('address'),200), email=required(f.get('email')),
        phone=f.get('phone','')[:20], username=required(f.get('username'),50), password_hash=password_hash(f.get('password','')),
        store=integer(f.get('store_id')), method=payment_method(f.get('method')))

def payment_method(value):
    require(value in ('Credit Card','Debit Card','Cash'), 'Invalid payment method')
    return value

def catalog(c, store, query='', make='', model='', year=''):
    params = dict(store=integer(store), q='%'+query+'%', exact=query)
    sql = '''SELECT p.*, COALESCE(i.amount_stocked,0) AS stock, COALESCE(i.reorder_level,5) AS reorder_level
    FROM Part p LEFT JOIN Inventory i ON i.part_id=p.part_id AND i.store_id=:store
    WHERE (CAST(p.part_id AS CHAR)=:exact OR p.part_name LIKE :q OR p.category LIKE :q)'''
    if make or model or year:
        params.update(make=required(make,60), model=required(model,60), year=integer(year,1886,2100))
        sql += ''' AND EXISTS(SELECT 1 FROM Part_Compatibility pc WHERE pc.part_id=p.part_id
        AND pc.make=:make AND pc.model=:model AND pc.year=:year)'''
    return rows(c, sql+' ORDER BY p.part_id', **params)

def checkout(auth, store, cart, token, f, fail_hook=None):
    require(cart, 'Cart is empty')
    store = integer(store)
    require(len(token) == 64, 'Invalid submission token')
    with engine.begin() as c:
        a = identity(c,auth)
        require(a['kind']=='Customer')
        # Serialize submissions by customer before checking the unique token.
        run(c,'SELECT customer_id FROM Customer WHERE customer_id=:id FOR UPDATE',id=a['customer_id'])
        old = one(c,'SELECT customer_order_id FROM Customer_Orders WHERE customer_id=:id AND submission_token=:t',id=a['customer_id'],t=token)
        if old:
            return old['customer_order_id']
        require(f.get('decision')=='Approved','Payment declined; no order placed')
        method=payment_method(f.get('method'))
        fulfillment=f.get('fulfillment')
        require(fulfillment in ('Pickup','Delivery'),'Choose pickup or delivery')
        address=required(f.get('delivery_address') or a['address'],200)
        billing=required(f.get('billing_address') or a['address'],200)
        last_four=f.get('last_four','')
        expiry=f.get('expiry','')
        card_type=f.get('card_type','')
        if method!='Cash':
            require(len(last_four)==4 and last_four.isascii() and last_four.isdigit(),'Enter exactly four synthetic card digits')
            try:
                exp=date.fromisoformat(expiry+'-01')
                require((exp.year,exp.month)>=(date.today().year,date.today().month),'Card expiry is in the past')
            except ValueError:
                raise RuleError('Expiry must be YYYY-MM')
            card_type=required(card_type,30)
        else:
            last_four=expiry=card_type=None
        lines=[]
        for part, qty in sorted(cart.items(),key=lambda x:int(x[0])):
            part,qty=integer(part),integer(qty)
            p=one(c,'''SELECT p.price,i.amount_stocked FROM Inventory i JOIN Part p USING(part_id)
            WHERE i.store_id=:s AND i.part_id=:p FOR UPDATE''',s=store,p=part)
            require(p and p['amount_stocked']>=qty,f'Insufficient stock for part {part}')
            lines.append((part,qty,p['price']))
        total=sum((price*qty for _,qty,price in lines),Decimal('0'))
        oid=run(c,'''INSERT INTO Customer_Orders(store_id,customer_id,placement_date,payment,fulfillment_method,delivery_address,submission_token)
        VALUES(:s,:u,CURRENT_DATE,:m,:f,:a,:t)''',s=store,u=a['customer_id'],m=method,f=fulfillment,a=address,t=token).lastrowid
        for part,qty,price in lines:
            run(c,'INSERT INTO Customer_Order_Item VALUES(:o,:p,:price,:q)',o=oid,p=part,price=price,q=qty)
            run(c,'UPDATE Inventory SET amount_stocked=amount_stocked-:q WHERE store_id=:s AND part_id=:p',q=qty,s=store,p=part)
        if fail_hook:
            fail_hook()
        run(c,'''INSERT INTO Payment(customer_order_id,method,amount,billing_address,card_type,last_four,expiry)
        VALUES(:o,:m,:v,:a,:ct,:lf,:ex)''',o=oid,m=method,v=total,a=billing,ct=card_type,lf=last_four,ex=expiry)
        return oid

def authorized_order(c, auth, oid, lock=False):
    a=identity(c,auth)
    o=one(c,'SELECT * FROM Customer_Orders WHERE customer_order_id=:o'+(' FOR UPDATE' if lock else ''),o=integer(oid))
    require(o is not None,'Order not found')
    require((a['kind']=='Customer' and o['customer_id']==a['customer_id']) or
            (a['kind']=='Employee' and o['store_id']==a['store_id']))
    return a,o

def order_detail(auth,oid):
    with engine.connect() as c:
        _,o=authorized_order(c,auth,oid)
        return dict(order=o,lines=rows(c,'''SELECT i.*,p.part_name FROM Customer_Order_Item i JOIN Part p USING(part_id)
        WHERE customer_order_id=:o''',o=oid),payment=rows(c,'SELECT method,amount,billing_address,card_type,last_four,expiry FROM Payment WHERE customer_order_id=:o',o=oid),
        refunds=rows(c,'''SELECT r.return_id,r.return_date,i.part_id,i.quantity,i.reason,i.restock,i.refund_amount
        FROM Customer_Return r JOIN Return_Item i USING(return_id) WHERE r.customer_order_id=:o''',o=oid))

def change_order(auth,oid,target):
    with engine.begin() as c:
        a,o=authorized_order(c,auth,oid,True)
        if target=='Cancelled':
            require(o['delivery_status']=='Pending','Only pending orders can be cancelled')
            for i in rows(c,'SELECT * FROM Customer_Order_Item WHERE customer_order_id=:o ORDER BY part_id',o=oid):
                run(c,'UPDATE Inventory SET amount_stocked=amount_stocked+:q WHERE store_id=:s AND part_id=:p',q=i['quantity'],s=o['store_id'],p=i['part_id'])
        else:
            require(a['kind']=='Employee')
            allowed = {'Pending':'Delivered'} if o['fulfillment_method']=='Pickup' else {'Pending':'Shipped','Shipped':'Delivered'}
            require(allowed.get(o['delivery_status'])==target,'Invalid fulfillment transition')
        run(c,'''UPDATE Customer_Orders SET delivery_status=:t,delivery_date=:d WHERE customer_order_id=:o''',t=target,d=date.today() if target=='Delivered' else None,o=oid)

def return_item(auth,oid,f):
    with engine.begin() as c:
        a,o=authorized_order(c,auth,oid,True)
        require(a['kind']=='Employee','A clerk records returns at the order branch')
        require(o['delivery_status']=='Delivered','Returns require a completed order')
        part=integer(f.get('part_id')); qty=integer(f.get('quantity'))
        line=one(c,'SELECT * FROM Customer_Order_Item WHERE customer_order_id=:o AND part_id=:p',o=oid,p=part)
        used=one(c,'SELECT COALESCE(SUM(quantity),0) AS n FROM Return_Item WHERE customer_order_id=:o AND part_id=:p',o=oid,p=part)['n']
        require(line and qty+used<=line['quantity'],'Return exceeds purchased quantity')
        rid=run(c,'INSERT INTO Customer_Return(customer_order_id,return_date) VALUES(:o,CURRENT_DATE)',o=oid).lastrowid
        restock=f.get('restock')=='yes'
        run(c,'''INSERT INTO Return_Item VALUES(:r,:o,:p,:q,:reason,:restock,:refund)''',r=rid,o=oid,p=part,q=qty,reason=required(f.get('reason'),200),restock=restock,refund=line['price']*qty)
        if restock:
            run(c,'UPDATE Inventory SET amount_stocked=amount_stocked+:q WHERE store_id=:s AND part_id=:p',q=qty,s=o['store_id'],p=part)

def purchase(auth,f,copy_id=None):
    with engine.begin() as c:
        a=identity(c,auth,employee=True,manager=True)
        if copy_id:
            old=one(c,'SELECT * FROM Store_Orders WHERE store_order_id=:o AND store_id=:s',o=integer(copy_id),s=a['store_id'])
            require(old is not None,'Purchase not found')
            supplier=old['supplier_id']
            items=rows(c,'SELECT part_id,quantity FROM Store_Orders_Item WHERE store_order_id=:o',o=copy_id)
        else:
            supplier=integer(f.get('supplier_id'))
            items=[dict(part_id=integer(f.get('part_id')),quantity=integer(f.get('quantity')))]
        lines=[]
        for i in items:
            sp=one(c,'SELECT unit_cost FROM Supplier_Part WHERE supplier_id=:s AND part_id=:p',s=supplier,p=i['part_id'])
            require(sp is not None,'Supplier does not carry this part')
            lines.append(dict(i,cost=sp['unit_cost']))
        oid=run(c,'''INSERT INTO Store_Orders(store_id,placement_date,cost,supplier_id) VALUES(:s,CURRENT_DATE,:v,:supplier)''',s=a['store_id'],v=sum(i['cost']*i['quantity'] for i in lines),supplier=supplier).lastrowid
        for i in lines:
            run(c,'INSERT INTO Store_Orders_Item VALUES(:o,:part_id,:cost,:quantity)',o=oid,**i)
        return oid

def change_purchase(auth,oid,target):
    require(target in ('Delivered','Cancelled'),'Invalid purchase status')
    with engine.begin() as c:
        a=identity(c,auth,employee=True,manager=True)
        o=one(c,'SELECT * FROM Store_Orders WHERE store_order_id=:o AND store_id=:s FOR UPDATE',o=integer(oid),s=a['store_id'])
        require(o is not None,'Purchase not found')
        if o['delivery_status']==target:
            return
        require(o['delivery_status']=='Pending','Purchase is no longer pending')
        if target=='Delivered':
            for i in rows(c,'SELECT * FROM Store_Orders_Item WHERE store_order_id=:o ORDER BY part_id',o=oid):
                run(c,'''INSERT INTO Inventory(store_id,part_id,amount_stocked,reorder_level) VALUES(:s,:p,:q,5)
                ON DUPLICATE KEY UPDATE amount_stocked=amount_stocked+:q''',s=a['store_id'],p=i['part_id'],q=i['quantity'])
        run(c,'UPDATE Store_Orders SET delivery_status=:t,delivery_date=:d WHERE store_order_id=:o',t=target,d=date.today() if target=='Delivered' else None,o=oid)

def administer(auth,action,f):
    with engine.begin() as c:
        a=identity(c,auth)
        if action=='profile':
            require(a['kind']=='Customer')
            run(c,'''UPDATE Customer SET name=:n,address=:ad,email=:e,phone=:p,pref_store_id=:s,pref_payment_method=:m
            WHERE customer_id=:u''',n=required(f.get('name')),ad=required(f.get('address'),200),e=required(f.get('email')),p=f.get('phone','')[:20],s=integer(f.get('store_id')),m=payment_method(f.get('method')),u=a['customer_id'])
        elif action=='vehicle':
            require(a['kind']=='Customer')
            run(c,'INSERT INTO Customer_Vehicle(customer_id,make,model,year) VALUES(:u,:ma,:mo,:y)',u=a['customer_id'],ma=required(f.get('make'),60),mo=required(f.get('model'),60),y=integer(f.get('year'),1886,2100))
        elif action=='delete_vehicle':
            require(a['kind']=='Customer')
            run(c,'DELETE FROM Customer_Vehicle WHERE vehicle_id=:v AND customer_id=:u',v=integer(f.get('vehicle_id')),u=a['customer_id'])
        else:
            require(a['kind']=='Employee' and a['role']=='Manager')
            if action=='clerk':
                values=dict(n=required(f.get('name')),d=required(f.get('department'),50),u=required(f.get('username'),50),s=a['store_id'])
                if f.get('employee_id'):
                    eid=integer(f['employee_id'])
                    target=one(c,"SELECT * FROM Employee WHERE employee_id=:e AND store_id=:s AND role='Clerk'",e=eid,s=a['store_id'])
                    require(target is not None,'Clerk not found in your store')
                    run(c,"UPDATE Employee SET name=:n,department=:d,username=:u WHERE employee_id=:e AND store_id=:s AND role='Clerk'",e=eid,**values)
                    if f.get('password'):
                        run(c,'UPDATE Employee SET password_hash=:p WHERE employee_id=:e',p=password_hash(f['password']),e=eid)
                else:
                    run(c,"INSERT INTO Employee(store_id,name,department,role,username,password_hash) VALUES(:s,:n,:d,'Clerk',:u,:p)",p=password_hash(f.get('password','')),**values)
            elif action=='delete_clerk':
                result=run(c,"DELETE FROM Employee WHERE employee_id=:e AND store_id=:s AND role='Clerk'",e=integer(f.get('employee_id')),s=a['store_id'])
                require(result.rowcount==1,'Clerk not found in your store')
            elif action=='part':
                values=dict(n=required(f.get('part_name')),d=required(f.get('description'),2000),ca=required(f.get('category'),50),b=required(f.get('brand'),50),co=f.get('part_condition'),p=money(f.get('price')))
                require(values['co'] in ('New','Rebuilt'),'Invalid condition')
                if f.get('part_id'):
                    result=run(c,'UPDATE Part SET part_name=:n,description=:d,category=:ca,brand=:b,part_condition=:co,price=:p WHERE part_id=:id',id=integer(f['part_id']),**values)
                    require(result.rowcount==1,'Part not found')
                else:
                    run(c,'INSERT INTO Part(part_name,description,category,brand,part_condition,price) VALUES(:n,:d,:ca,:b,:co,:p)',**values)
            elif action=='stock':
                run(c,'''INSERT INTO Inventory VALUES(:s,:p,:q,:r) ON DUPLICATE KEY UPDATE amount_stocked=:q,reorder_level=:r''',s=a['store_id'],p=integer(f.get('part_id')),q=integer(f.get('quantity'),0),r=integer(f.get('reorder_level'),0))
            elif action=='supplier':
                values=dict(n=required(f.get('name')),p=f.get('phone','')[:30],ad=required(f.get('address'),200))
                if f.get('supplier_id'):
                    result=run(c,'UPDATE Supplier SET name=:n,phone=:p,address=:ad WHERE supplier_id=:s',s=integer(f['supplier_id']),**values)
                    require(result.rowcount==1,'Supplier not found')
                else:
                    run(c,'INSERT INTO Supplier(name,phone,address) VALUES(:n,:p,:ad)',**values)
            elif action=='supplier_part':
                run(c,'''INSERT INTO Supplier_Part VALUES(:s,:p,:v) ON DUPLICATE KEY UPDATE unit_cost=:v''',s=integer(f.get('supplier_id')),p=integer(f.get('part_id')),v=money(f.get('unit_cost')))
            elif action=='compatibility':
                run(c,'INSERT INTO Part_Compatibility VALUES(:p,:ma,:mo,:y)',p=integer(f.get('part_id')),ma=required(f.get('make'),60),mo=required(f.get('model'),60),y=integer(f.get('year'),1886,2100))
            else:
                raise RuleError('Unknown action')

def reports(auth,period='daily',all_stores=False):
    require(period in ('daily','weekly','monthly'),'Invalid reporting period')
    with engine.connect() as c:
        a=identity(c,auth,employee=True)
        require(not all_stores or a['role']=='Manager')
        where='1=1' if all_stores else 'o.store_id=:s'
        bucket={'daily':'DATE(o.placement_date)','weekly':"DATE_SUB(o.placement_date, INTERVAL WEEKDAY(o.placement_date) DAY)",'monthly':"DATE_FORMAT(o.placement_date,'%Y-%m-01')"}[period]
        sales=rows(c,f'''SELECT o.store_id,{bucket} AS period,COUNT(DISTINCT o.customer_order_id) AS orders,
        SUM(i.price*i.quantity) AS gross_sales FROM Customer_Orders o JOIN Customer_Order_Item i USING(customer_order_id)
        WHERE {where} AND o.delivery_status<>'Cancelled' GROUP BY o.store_id,period ORDER BY period DESC''',s=a['store_id'])
        refunds=rows(c,f'''SELECT o.store_id,{bucket} AS original_sale_period, SUM(ri.refund_amount) AS refunds
        FROM Customer_Orders o JOIN Return_Item ri USING(customer_order_id) WHERE {where}
        GROUP BY o.store_id,original_sale_period''',s=a['store_id'])
        refund_map={(r['store_id'],str(r['original_sale_period'])):r['refunds'] for r in refunds}
        sales=[dict(r,refunds=refund_map.get((r['store_id'],str(r['period'])),Decimal('0')),
                    net_sales=r['gross_sales']-refund_map.get((r['store_id'],str(r['period'])),Decimal('0'))) for r in sales]
        scope='' if all_stores else ' WHERE store_id=:s'
        inventory=rows(c,'SELECT * FROM Inventory'+scope+' ORDER BY store_id,part_id',s=a['store_id'])
        roster=rows(c,'SELECT employee_id,store_id,name,department,role,username FROM Employee'+scope+' ORDER BY store_id,employee_id',s=a['store_id'])
        return dict(sales=sales,inventory=inventory,low_stock=[r for r in inventory if r['amount_stocked']<r['reorder_level']],roster=roster)
