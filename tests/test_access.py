import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from access import password_hash, valid_hash, verify_password

class AccessTest(unittest.TestCase):
    def test_hash(self):
        password='演示测试密码-not-a-real-secret'
        encoded=password_hash(password)
        self.assertTrue(valid_hash(encoded))
        self.assertTrue(verify_password(password,encoded))
        self.assertFalse(verify_password('错误密码',encoded))
        self.assertNotEqual(encoded,password_hash(password))
        self.assertFalse(valid_hash('invalid'))

    def test_online_requires_password(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,'app.py'],env={**os.environ,'WORKBENCH_ONLINE':'1','WORKBENCH_PASSWORD_HASH':'','WORKBENCH_DATA_DIR':directory},capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('拒绝无密码启动',result.stderr)

    def test_all_private_routes_require_auth(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            password='demo-only-test-password-123'
            proc=subprocess.Popen([sys.executable,'app.py'],env={**os.environ,'WORKBENCH_ONLINE':'1','WORKBENCH_USERNAME':'tester','WORKBENCH_PASSWORD_HASH':password_hash(password),'WORKBENCH_DATA_DIR':directory,'HOST':'127.0.0.1','PORT':str(port)},stdout=subprocess.DEVNULL)
            base=f'http://127.0.0.1:{port}'
            try:
                for _ in range(100):
                    try:
                        with urlopen(base+'/healthz',timeout=1) as r:self.assertEqual(r.status,200)
                        break
                    except OSError:time.sleep(.03)
                else:self.fail('认证测试服务未启动')
                for path in ['/','/app.js','/style.css','/api/products','/api/backup','/api/export.csv','/api/package/missing']:
                    with self.assertRaises(HTTPError) as error:urlopen(base+path)
                    self.assertEqual(error.exception.code,401,path)
                for path in ['/api/products','/api/delete','/api/restore','/api/profit']:
                    with self.assertRaises(HTTPError) as error:urlopen(Request(base+path,data=b'{}',headers={'Content-Type':'application/json'}))
                    self.assertEqual(error.exception.code,401,path)
                for token in ['not-base64','Basic not-base64','Bearer x','Basic '+base64.b64encode(b'tester:wrong').decode()]:
                    with self.assertRaises(HTTPError) as error:urlopen(Request(base+'/api/backup',headers={'Authorization':token}))
                    self.assertEqual(error.exception.code,401)
                auth='Basic '+base64.b64encode(('tester:'+password).encode()).decode()
                with urlopen(Request(base+'/',headers={'Authorization':auth})) as r:self.assertIn('Ozon 秋冬袜子工作台',r.read().decode())
                with urlopen(Request(base+'/api/products',headers={'Authorization':auth,'Content-Type':'application/json'},data=json.dumps({'name':'认证测试演示','demo':True}).encode())) as r:
                    product=json.load(r)
                with urlopen(Request(base+'/api/backup',headers={'Authorization':auth})) as r:
                    self.assertEqual(json.load(r)['products'][0]['id'],product['id'])
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base+'/api/delete',headers={'Authorization':auth,'Origin':'https://untrusted.example','Content-Type':'application/json'},data=json.dumps({'id':product['id']}).encode()))
                self.assertEqual(error.exception.code,403)
            finally:
                proc.terminate();proc.wait(timeout=5)

if __name__=='__main__':unittest.main()
