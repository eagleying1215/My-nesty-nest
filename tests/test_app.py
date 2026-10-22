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
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import profit, validate

class WorkbenchTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with socket.socket() as s: s.bind(('127.0.0.1',0)); self.port=s.getsockname()[1]
        self.start()
    def start(self):
        self.proc=subprocess.Popen([sys.executable,'app.py'],env={**os.environ,'WORKBENCH_DATA_DIR':self.temp.name,'PORT':str(self.port)},stdout=subprocess.DEVNULL)
        for _ in range(100):
            try: self.request('products');return
            except OSError: time.sleep(.03)
        self.fail('服务未启动')
    def tearDown(self):
        self.proc.terminate();self.proc.wait();self.temp.cleanup()
    def request(self,path,body=None):
        req=Request(f'http://127.0.0.1:{self.port}/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req) as r:
            data=r.read()
            return data.decode('utf-8-sig') if path=='export.csv' else json.loads(data)
    def product(self):
        return dict(name='演示测试袜',demo=True,status='候选',purchase=5,dropship=1,packaging=2,domestic=3,logistics=9,pairs=2,sale=500,rate=10,platformRate=10,fixed=10,adsRate=5,lossRate=5,verification={'state':'未核实','dropshipSupport':'未核实'},checks={'类目':'待核实'},imageTasks={'0':'制作中'},ruTitle='Носки',images=[{'name':'演示实拍','src':'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZioAAAAASUVORK5CYII='}])
    def test_crud_persistence_backup_export(self):
        p=self.request('products',self.product()); self.assertTrue(p['id'])
        p['notes']='修改后';p['code']='=SUM(1,1)';self.request('products',p)
        self.assertEqual(self.request('products')[0]['notes'],'修改后')
        self.proc.terminate();self.proc.wait();self.start()
        self.assertEqual(self.request('products')[0]['id'],p['id'])
        backup=self.request('backup')
        exported=self.request('export.csv'); self.assertIn('非 Ozon 导入模板',exported);self.assertIn("'=SUM",exported);self.assertIn('演示',exported);self.assertIn('待补充',exported)
        package=self.request('package/'+p['id']);self.assertEqual(package['product']['ruTitle'],'Носки');self.assertTrue(package['product']['images'][0]['src'].startswith('data:image'))
        self.request('delete',{'id':p['id']});self.assertEqual(self.request('products'),[])
        self.request('restore',backup);self.assertEqual(self.request('products'),backup['products'])
        invalid=json.loads(json.dumps(backup));invalid['products'].append({'name':'非法','id':'bad','purchase':-1})
        with self.assertRaises(HTTPError):self.request('restore',invalid)
        self.assertEqual(self.request('products'),backup['products'])
        with self.assertRaises(HTTPError): self.request('restore',{'format':'other','products':[]})
    def test_profit(self):
        p=self.product();r=self.request('profit',p)
        self.assertTrue(r['complete']);self.assertEqual(r['costCny'],25);self.assertEqual(r['profitRub'],140);self.assertEqual(r['profitCny'],14);self.assertEqual(r['margin'],28);self.assertEqual(r['breakEvenRub'],325)
        single=profit(p,1);self.assertEqual(single['costCny'],20);self.assertEqual(single['profitRub'],190)
        p['logistics']=None;self.assertFalse(self.request('profit',p)['complete'])
        p['logistics']=0;self.assertTrue(self.request('profit',p)['complete'])
        p['adsRate']=90;self.assertFalse(self.request('profit',p)['complete'])
        p['rate']=0
        with self.assertRaises(HTTPError): self.request('profit',p)
    def test_validation(self):
        for patch in [{'name':''},{'pairs':1.5},{'rate':-1},{'verification':{'state':'自动通过'}},{'images':[{'src':'javascript:alert(1)'}]}]:
            with self.assertRaises(HTTPError):self.request('products',{**self.product(),**patch})
        with urlopen(f'http://127.0.0.1:{self.port}/') as r:self.assertIn('Ozon 秋冬袜子工作台',r.read().decode())

if __name__=='__main__':unittest.main()
