import unittest
from app import create_app, db
from app.models import User, Student, Hostel, Complaint, ComplaintResponse, Notice

class ComplaintsNoticesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Admin
        self.admin = User(username='admin_cn', email='adm_cn@aktu.ac.in', role='admin')
        self.admin.set_password('Admin@123')

        # Student
        self.student_u = User(username='std_cn', email='std_cn@aktu.ac.in', role='student')
        self.student_u.set_password('Pass123')
        db.session.add_all([self.admin, self.student_u])
        db.session.flush()

        self.student = Student(
            user_id=self.student_u.id,
            enrollment_no='ENR-CN-01',
            full_name='Complaint Tester',
            phone='9876543210',
            gender='male',
            branch='CSE',
            year=1,
            semester=1,
            guardian_name='Guard',
            guardian_phone='9876543210',
            address='Kanpur'
        )
        db.session.add(self.student)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_admin(self):
        return self.client.post('/auth/login', data={'identity': 'admin_cn', 'password': 'Admin@123'}, follow_redirects=True)

    def login_student(self):
        return self.client.post('/auth/login', data={'identity': 'std_cn', 'password': 'Pass123'}, follow_redirects=True)

    def test_complaint_lifecycle(self):
        # 1. Student files complaint
        self.login_student()
        res_post = self.client.post('/student/complaints/new', data={
            'title': 'Leaking Washroom Pipe',
            'category': 'plumbing',
            'priority': 'high',
            'description': 'Water leaking continuously on 1st floor'
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)

        # Verify DB
        c = Complaint.query.filter_by(title='Leaking Washroom Pipe').first()
        self.assertIsNotNone(c)
        self.assertEqual(c.status, 'pending')

        # Logout student and login as admin
        self.client.get('/auth/logout')
        self.login_admin()
        res_resp = self.client.post(f'/admin/complaints/{c.id}', data={
            'response_text': 'Plumber fixed the pipe washer. All clear.',
            'status': 'resolved'
        }, follow_redirects=True)
        self.assertEqual(res_resp.status_code, 200)

        c_updated = Complaint.query.get(c.id)
        self.assertEqual(c_updated.status, 'resolved')
        self.assertEqual(c_updated.responses.count(), 1)

    def test_notice_publishing(self):
        self.login_admin()
        res = self.client.post('/admin/notices/add', data={
            'title': 'Campus Gate Closing Advisory',
            'category': 'urgent',
            'target_audience': 'all',
            'content': 'All residents must report before 9:30 PM tonight.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        n = Notice.query.filter_by(title='Campus Gate Closing Advisory').first()
        self.assertIsNotNone(n)
        self.assertEqual(n.target_audience, 'all')

    def test_analytics_api_endpoint(self):
        self.login_admin()
        res = self.client.get('/admin/api/analytics-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertIn('occupancy', json_data)
        self.assertIn('complaints', json_data)
        self.assertIn('revenue', json_data)

if __name__ == '__main__':
    unittest.main()
