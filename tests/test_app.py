import sys, tempfile, threading, unittest, json, urllib.request, urllib.error, http.cookiejar
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class Client:
    def __init__(self,url):
        self.url=url; self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,path,method='GET',data=None,header=True):
        r=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(data or {}).encode() if method!='GET' else None,method=method,headers={'Content-Type':'application/json',**({'X-Inmobi-Request':'1'} if header else {})})
        try:
            with self.opener.open(r) as res:return res.status,json.load(res)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def login(self,role):return self.call('login','POST',{'email':role+'@inmobi.test','password':app.DEMO_PASSWORD})

class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(); app.DB=Path(cls.temp.name)/'test.sqlite3';app.init_db(True)
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler); threading.Thread(target=cls.server.serve_forever,daemon=True).start(); cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
    def test_end_to_end(self):
        guest,buyer,seller,admin,other=[Client(self.url) for _ in range(5)]
        self.assertEqual(len(guest.call('properties')[1]),6)
        self.assertEqual(guest.call('admin')[0],401)
        self.assertEqual(guest.call('login','POST',{'email':'comprador@inmobi.test','password':'bad'})[0],401)
        for role,client in [('comprador',buyer),('vendedor',seller),('administrador',admin)]:
            status,data=client.login(role);self.assertEqual(status,200);self.assertEqual(data['user']['role'],role);self.assertNotIn('password',data['user'])
        self.assertEqual(buyer.call('admin')[0],403)
        self.assertEqual(buyer.call('properties','POST',{})[0],403)
        self.assertEqual(guest.call('register','POST',{'name':'Fake Admin','email':'x@example.test','password':'Pass12345','role':'administrador'})[0],400)
        payload={'title':'Terreno de integración','department':'San Miguel','city':'San Miguel','price':25000,'area':500,'width':20,'length':25,'kind':'Residencial','description':'Terreno para la prueba automatizada.','photos':['/static/campo.svg'],'lat':13.47,'lon':-88.17}
        self.assertEqual(seller.call('properties','POST',payload,header=False)[0],403)
        self.assertEqual(seller.call('properties','POST',{**payload,'price':-1})[0],400)
        st,data=seller.call('properties','POST',payload);self.assertEqual(st,200);pid=data['id']
        self.assertEqual(other.call('register','POST',{'name':'Otro vendedor','email':'otro@example.test','password':'Pass12345','role':'vendedor','phone':'70000000'})[0],200)
        self.assertEqual(other.call(f'properties/{pid}','PATCH',{'status':'vendida'})[0],403)
        self.assertEqual(buyer.call(f'favorites/{pid}','POST')[0],200)
        self.assertEqual(buyer.call(f'favorites/{pid}','POST')[0],200)
        self.assertEqual(len(buyer.call('favorites')[1]),1)
        self.assertEqual(seller.call(f'properties/{pid}','PUT',{**payload,'price':20000})[0],200)
        notes=buyer.call('notifications')[1];self.assertEqual(len(notes),1);self.assertEqual(notes[0]['property_id'],pid)
        self.assertEqual(buyer.call('notifications/read','POST')[0],200);self.assertEqual(buyer.call('notifications')[1][0]['is_read'],1)
        self.assertEqual(seller.call(f'properties/{pid}','PUT',{**payload,'price':30000})[0],200);self.assertEqual(len(buyer.call('notifications')[1]),1)
        self.assertEqual(seller.call(f'properties/{pid}','PATCH',{'status':'pausada'})[0],200);self.assertNotIn(pid,[p['id'] for p in guest.call('properties')[1]])
        self.assertEqual(seller.call(f'properties/{pid}','PATCH',{'status':'activa'})[0],200)
        self.assertEqual(admin.call(f'properties/{pid}','PATCH',{'status':'rechazada'})[0],200)
        self.assertEqual(seller.call(f'properties/{pid}','PATCH',{'status':'activa'})[0],403)
        self.assertEqual(buyer.call(f'favorites/{pid}','DELETE')[0],200)
        buyer_id=buyer.call('me')[1]['user']['id'];self.assertEqual(buyer.call('role-request','POST',{'phone':'70000000'})[0],200)
        self.assertEqual(admin.call(f'admin/requests/{buyer_id}','PATCH',{'status':'aprobada'})[0],200);self.assertEqual(buyer.call('me')[1]['user']['role'],'vendedor')
        self.assertEqual(admin.call(f'admin/users/{buyer_id}','PATCH',{'active':False})[0],200);self.assertIsNone(buyer.call('me')[1]['user'])
        self.assertEqual(buyer.login('comprador')[0],401)
        with app.db() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM price_history WHERE property_id=?',(pid,)).fetchone()[0],2)
            self.assertNotEqual(c.execute('SELECT password FROM users WHERE id=?',(buyer_id,)).fetchone()[0],app.DEMO_PASSWORD)
        self.assertEqual(seller.call('logout','POST')[0],200);self.assertIsNone(seller.call('me')[1]['user'])

if __name__=='__main__':unittest.main()
