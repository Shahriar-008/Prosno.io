#!/usr/bin/env python
"""
Create admin user for local testing
"""
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    existing = User.query.filter_by(username='Admin').first()
    if existing:
        print('Admin user already exists')
    else:
        user = User(username='Admin', email='admin@prosno.io', is_admin=True)
        user.set_password('12345')
        db.session.add(user)
        db.session.commit()
        print('✓ Admin user created')
        print('  Username: Admin')
        print('  Password: 12345')
