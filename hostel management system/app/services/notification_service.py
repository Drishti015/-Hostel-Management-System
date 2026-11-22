from app.models import db, Notification

class NotificationService:
    """Service to generate, query, and manage user in-app notifications"""

    @staticmethod
    def create_notification(user_id, title, message, type='info', link=None):
        """Creates and stages a notification"""
        if not user_id:
            return None
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link
        )
        db.session.add(notification)
        return notification

    @staticmethod
    def get_unread_count(user_id):
        if not user_id:
            return 0
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @staticmethod
    def get_recent_notifications(user_id, limit=5):
        if not user_id:
            return []
        return Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(limit).all()

    @staticmethod
    def mark_as_read(notification_id, user_id):
        notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if notif:
            notif.is_read = True
            db.session.commit()
            return True
        return False

    @staticmethod
    def mark_all_as_read(user_id):
        if not user_id:
            return
        Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
        db.session.commit()

