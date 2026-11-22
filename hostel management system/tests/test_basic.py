import unittest
from app import create_app, db
from app.models import User, Student, Hostel

class BasicTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_exists(self):
        self.assertFalse(self.app is None)

    def test_landing_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'HostelEase HMS', response.data)

    def test_login_page(self):
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Portal Sign In', response.data)

    def test_user_password_hashing(self):
        u = User(username='test_user', email='test@aktu.ac.in', role='student')
        u.set_password('Pass1234')
        self.assertTrue(u.check_password('Pass1234'))
        self.assertFalse(u.check_password('WrongPass'))

if __name__ == '__main__':
    unittest.main()

