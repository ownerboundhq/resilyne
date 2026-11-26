import unittest
from finance.integrations import read_sample,CATALOG

class IntegrationTests(unittest.TestCase):
    def fake(self,expected_url,response,expected_header="Authorization",expected_body=False):
        def call(url,headers,body=None):
            self.assertTrue(url.startswith(expected_url),url)
            self.assertIn(expected_header,headers)
            self.assertEqual(body is not None,expected_body)
            if body: self.assertNotIn(b"mutation",body)
            return response
        return call
    def test_sheets(self):
        r=read_sample("Google Sheets",{"spreadsheet":"abcdefghijkl","range":"Sheet1!A1:D20"},"fake-token",self.fake("https://sheets.googleapis.com/v4/spreadsheets/abcdefghijkl/values/Sheet1%21A1%3AD20",{"values":[["Invoice","Amount"],["A",50]]}))
        self.assertEqual(r["count"],2)
        self.assertEqual(r["records"][1][1],50)
    def test_shopify(self):
        response={"data":{"orders":{"nodes":[{"id":"1","createdAt":"2026-01-01","currentTotalPriceSet":{"shopMoney":{"amount":"123.45","currencyCode":"CAD"}}}],"pageInfo":{"hasNextPage":True}}}}
        r=read_sample("Shopify",{"shop":"demo.myshopify.com"},"fake-token",self.fake("https://demo.myshopify.com/admin/api/2026-10/graphql.json",response,"X-Shopify-Access-Token",True))
        self.assertEqual(r["records"][0]["total"],"123.45")
        self.assertTrue(r["truncated"])
    def test_stripe(self):
        row={"id":"txn_demo","created":123,"currency":"cad","amount":1000,"fee":30,"net":970,"type":"charge"}
        r=read_sample("Stripe",{},"rk_test_12345678",self.fake("https://api.stripe.com/v1/balance_transactions",{"data":[row],"has_more":False}))
        self.assertEqual(r["records"][0]["net"],970)
    def test_quickbooks(self):
        r=read_sample("QuickBooks Online",{"realm":"12345"},"fake-token",self.fake("https://sandbox-quickbooks.api.intuit.com/v3/company/12345/query?",{"QueryResponse":{"Invoice":[{"Id":"1","TxnDate":"2026-01-01","TotalAmt":50,"Balance":25}]}}))
        self.assertEqual(r["records"][0]["balance"],25)
    def test_reject_unsafe_inputs_without_network(self):
        def forbidden(*a): self.fail("Unexpected network request")
        for p,c,t in [
            ("Shopify",{"shop":"evil.example"},"fake-token"),
            ("Stripe",{},"sk_live_12345678"),
            ("Google Sheets",{"spreadsheet":"abcdefghijkl","range":"A1:ZZ999"},"fake-token"),
            ("QuickBooks Online",{"realm":"123/evil"},"fake-token"),
            ("Wave",{},"fake-token")]:
            with self.assertRaises(ValueError): read_sample(p,c,t,forbidden)
    def test_catalog(self):
        self.assertGreaterEqual(sum(map(len,CATALOG.values())),50)
