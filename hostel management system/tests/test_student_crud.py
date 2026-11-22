import unittest
from app import create_app, db
from app.models import User, Student

class StudentCRUDTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Create Admin
        self.admin = User(username='admin_test', email='adm@aktu.ac.in', role='admin')
        self.admin.set_password('Admin@123')
        db.session.add(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_admin(self):
        return self.client.post('/auth/login', data={
            'identity': 'admin_test',
            'password': 'Admin@123'
        }, follow_redirects=True)

    def test_student_lifecycle(self):
        # 1. Login as Admin
        res_login = self.login_admin()
        self.assertEqual(res_login.status_code, 200)

        # 2. View Student Directory
        res_list = self.client.get('/admin/students')
        self.assertEqual(res_list.status_code, 200)
        self.assertIn(b'Students Directory', res_list.data)

        # 3. Add Student Form GET
        res_add_get = self.client.get('/admin/students/add')
        self.assertEqual(res_add_get.status_code, 200)

        # 4. Add Student POST
        res_add_post = self.client.post('/admin/students/add', data={
            'username': 'manish_kumar',
            'email': 'manish@aktu.ac.in',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'full_name': 'Manish Kumar',
            'enrollment_no': 'AKTU2023CSE0999',
            'roll_no': '23000101999',
            'phone': '9876543219',
            'gender': 'male',
            'branch': 'Computer Science & Engineering',
            'year': 2,
            'semester': 3,
            'guardian_name': 'Mr. R.K. Kumar',
            'guardian_phone': '9876543218',
            'address': 'Gorakhpur, UP',
            'blood_group': 'B+'
        }, follow_redirects=True)
        self.assertEqual(res_add_post.status_code, 200)
        self.assertIn(b'Manish Kumar', res_add_post.data)

        # 5. Verify database records
        st = Student.query.filter_by(enrollment_no='AKTU2023CSE0999').first()
        self.assertIsNotNone(st)
        self.assertEqual(st.full_name, 'Manish Kumar')
        self.assertEqual(st.user_account.email, 'manish@aktu.ac.in')

        # 6. View Dossier
        res_view = self.client.get(f'/admin/students/{st.id}')
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b'Student Dossier', res_view.data)

        # 7. Export CSV
        res_csv = self.client.get('/admin/students/export-csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn(b'AKTU2023CSE0999', res_csv.data)

if __name__ == '__main__':
    unittest.main()

