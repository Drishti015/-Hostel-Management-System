import os
from app import create_app, db

app = create_app(os.environ.get('FLASK_ENV', 'development'))

@app.cli.command("init-db")
def init_db():
    """CLI command to create all tables from SQLAlchemy models"""
    with app.app_context():
        db.create_all()
        print("All database tables created successfully.")

if __name__ == '__main__':
    # Run development server on port 5000
    app.run(host='127.0.0.1', port=5000, debug=False)

