import csv
import base64
import hmac
from access import valid_hash, verify_password
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).parent
DATA = Path(os.environ.get('WORKBENCH_DATA_DIR', ROOT / 'data'))
STATUSES = ['候选','待补资料','待核算','待买样','素材制作中','待上架','已提交','已上架','淘汰']
CHECKS = ['类目','必填属性','变体','成分','尺寸','销售数量','图片','价格','库存','配送','所需文件']
IMAGES = ['主图','整体版型','内里细节','材质','尺寸','包装或场景']
NUMBERS = ['purchase','dropship','packaging','domestic','logistics','weight','length','width','height','pairs','competitorPrice','sale','rate','platformRate','fixed','adsRate','lossRate']
COLUMNS = {'code':'商品编号','name':'名称','supplierUrl':'供货链接','supplier':'供应商','purchase':'采购价（人民币/双）','dropship':'代发费（人民币/单）','packaging':'包装费（人民币/单）','domestic':'国内运费（人民币/单）','logistics':'跨境物流费（人民币/单）','weight':'包装重量（克）','length':'包装长（厘米）','width':'包装宽（厘米）','height':'包装高（厘米）','material':'材质成分','color':'颜色','size':'尺码','pairs':'销售双数','competitorUrl':'竞品链接','competitorPrice':'竞品价格（卢布）','notes':'备注','status':'进度'}

def db():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATA / 'workbench.sqlite3')
    con.execute('CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    return con

def validate(p):
    if not isinstance(p, dict) or not str(p.get('name','')).strip():
        raise ValueError('请填写商品名称')
    if p.get('status', '候选') not in STATUSES:
        raise ValueError('无效进度')
    for k in NUMBERS:
        v=p.get(k)
        if v not in (None, ''):
            if isinstance(v,bool) or not isinstance(v,(float,int)) or not __import__('math').isfinite(v) or v < 0:
                raise ValueError(f'{k} 必须为非负数字')
    if p.get('pairs') not in (None,'') and (p['pairs'] < 1 or int(p['pairs']) != p['pairs']):
        raise ValueError('销售双数必须为正整数')
    if p.get('rate') not in (None,'') and p['rate'] <= 0:
        raise ValueError('汇率必须大于零')
    for k in ['platformRate','adsRate','lossRate']:
        if p.get(k) not in (None,'') and p[k] >= 100:
            raise ValueError('单项比例必须小于100%')
    supplier=p.get('verification',{})
    if not isinstance(supplier,dict) or supplier.get('state','未核实') not in ['未核实','通过','未通过'] or supplier.get('dropshipSupport','未核实') not in ['未核实','通过','未通过']:
        raise ValueError('无效供应商核验状态')
    checks=p.get('checks',{})
    if not isinstance(checks,dict) or any(v not in ['待核实','通过','未通过'] for v in checks.values()):
        raise ValueError('无效检查状态')
    images=p.get('images',[])
    if not isinstance(images,list) or len(images)>30:
        raise ValueError('每款最多30张图片')
    for item in images:
        if not isinstance(item,dict): raise ValueError('图片格式错误')
        src=item.get('src','')
        if not isinstance(src,str) or (src and not src.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,','data:image/gif;base64,'))):
            raise ValueError('仅接受本地 PNG/JPEG/WebP/GIF 图片')
    return p

def profit(p, pairs=None):
    required=['purchase','dropship','packaging','domestic','logistics','pairs','sale','rate','platformRate','fixed','adsRate','lossRate']
    missing=[k for k in required if p.get(k) in (None,'')]
    if missing: return {'complete':False,'missing':missing}
    n=pairs if pairs is not None else p['pairs']
    cost=p['purchase']*n+sum(p[k] for k in ['dropship','packaging','domestic','logistics'])
    ratio=sum(p[k] for k in ['platformRate','adsRate','lossRate'])/100
    if ratio>=1: return {'complete':False,'error':'各项比例之和须小于100%'}
    rub_cost=cost*p['rate']+p['fixed']
    gain=p['sale']*(1-ratio)-rub_cost
    return {'complete':True,'pairs':n,'costCny':round(cost,2),'profitRub':round(gain,2),'profitCny':round(gain/p['rate'],2),'margin':round(gain/p['sale']*100,2) if p['sale'] else None,'breakEvenRub':round(rub_cost/(1-ratio),2)}

def listing(p):
    return {'资料性质':'内部上架资料包，非 Ozon 可直接导入模板；平台规则须另行核实','product':p,'profit':profit(p),'图片任务模板':IMAGES,'平台检查默认':'待核实；通过仅表示用户自行核验，不代表平台认可'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def authorized(self):
        encoded=os.environ.get('WORKBENCH_PASSWORD_HASH','')
        if not encoded:return True
        try:
            scheme,token=self.headers.get('Authorization','').split(' ',1)
            if scheme.lower()!='basic' or len(token)>4096:raise ValueError()
            username,password=base64.b64decode(token,validate=True).decode().split(':',1)
            if (hmac.compare_digest(username.encode(),os.environ.get('WORKBENCH_USERNAME','owner').encode())
                    and verify_password(password,encoded)):
                return True
        except (ValueError,UnicodeError):
            pass
        self.send_response(401)
        self.send_header('WWW-Authenticate','Basic realm="Ozon Socks Workbench", charset="UTF-8"')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length','0')
        self.end_headers()
        return False
    def send(self,status,body,kind='application/json; charset=utf-8',filename=None):
        if not isinstance(body,bytes): body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if filename: self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def body(self):
        length=int(self.headers.get('Content-Length',0))
        if length>40*1024*1024: raise ValueError('请求超过40MB，请减少图片大小')
        return json.loads(self.rfile.read(length))
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/healthz':return self.send(200,{'status':'ok'})
        if not self.authorized():return
        if path.startswith('/api/'):
            with db() as con: products=[json.loads(r[0]) for r in con.execute('SELECT body FROM products ORDER BY rowid DESC')]
            if path=='/api/products': return self.send(200,products)
            if path=='/api/backup': return self.send(200,{'format':'ozon-socks-v1','created':datetime.now(timezone.utc).isoformat(),'products':products},filename='ozon-backup.json')
            if path=='/api/export.csv':
                out=io.StringIO(); w=csv.writer(out); w.writerow(['资料性质','数据标记',*COLUMNS.values()])
                def safe(v):
                    s='待补充' if v is None or v=='' else str(v)
                    return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
                for p in products: w.writerow(['内部资料，非 Ozon 导入模板','演示' if p.get('demo') else '个人录入',*[safe(p.get(k)) for k in COLUMNS]])
                return self.send(200,('\ufeff'+out.getvalue()).encode(),'text/csv; charset=utf-8','products-internal.csv')
            if path.startswith('/api/package/'):
                p=next((p for p in products if p['id']==unquote(path.split('/')[-1])),None)
                return self.send(200,listing(p),filename='listing-internal.json') if p else self.send(404,{'error':'商品不存在'})
            return self.send(404,{'error':'接口不存在'})
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if path not in files: return self.send(404,{'error':'不存在'})
        name,kind=files[path]; self.send(200,(ROOT/'static'/name).read_bytes(),kind)
    def do_POST(self):
        if not self.authorized():return
        # Restrict mutation to same origin; bind loopback by default.
        origin=self.headers.get('Origin')
        if origin and origin not in ('http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')):
            return self.send(403,{'error':'不允许跨站写入'})
        try:
            path=urlsplit(self.path).path; body=self.body()
            if path=='/api/profit': return self.send(200,profit(validate(body)))
            if path=='/api/products':
                p=validate(body); p['id']=p.get('id') or str(uuid.uuid4()); p['updated']=datetime.now(timezone.utc).isoformat()
                if not isinstance(p['id'],str): raise ValueError('商品ID格式错误')
                with db() as con: con.execute('INSERT OR REPLACE INTO products VALUES (?,?)',(p['id'],json.dumps(p,ensure_ascii=False,allow_nan=False)))
                return self.send(200,p)
            if path=='/api/delete':
                with db() as con: con.execute('DELETE FROM products WHERE id=?',(body['id'],))
                return self.send(200,{'ok':True})
            if path=='/api/restore':
                if body.get('format')!='ozon-socks-v1' or not isinstance(body.get('products'),list): raise ValueError('不是有效的工作台备份')
                items=[validate(p) for p in body['products']]
                ids=[p.get('id') for p in items]
                if any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids): raise ValueError('备份商品ID无效或重复')
                with db() as con:
                    con.execute('DELETE FROM products')
                    con.executemany('INSERT INTO products VALUES (?,?)',[(p['id'],json.dumps(p,ensure_ascii=False,allow_nan=False)) for p in items])
                return self.send(200,{'ok':True,'count':len(items)})
            self.send(404,{'error':'接口不存在'})
        except (ValueError,TypeError,KeyError) as e: self.send(400,{'error':str(e)})

def main(open_browser=False):
    host=os.environ.get('HOST','127.0.0.1'); port=int(os.environ.get('PORT','8000'))
    encoded=os.environ.get('WORKBENCH_PASSWORD_HASH','')
    if encoded and not valid_hash(encoded):
        raise SystemExit('密码摘要格式无效，请运行配置线上密码.py 重新生成配置')
    if (os.environ.get('WORKBENCH_ONLINE')=='1' or host not in ['127.0.0.1','localhost','::1']) and not encoded:
        raise SystemExit('线上或非本机监听必须设置 WORKBENCH_PASSWORD_HASH；拒绝无密码启动')
    db().close()
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'秋冬袜子工作台已启动，端口 {port}',flush=True)
    if open_browser:
        import threading
        import webbrowser
        threading.Timer(0.5, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__=='__main__':
    main()
