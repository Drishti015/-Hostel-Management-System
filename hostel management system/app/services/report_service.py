from sqlalchemy import func
from app.models import db, Hostel, Room, Bed, FeeRecord, Complaint

class ReportService:
    """Service generating analytical datasets for executive dashboard and Chart.js"""

    @staticmethod
    def get_dashboard_chart_data():
        """
        Gathers:
        1. Hostel Block Occupancy: Block names, occupied beds, vacant beds
        2. Complaint Categories Distribution: electrical, plumbing, etc.
        3. Monthly Fee Revenue Trends
        """
        # 1. Occupancy Data
        hostels = Hostel.query.all()
        occupancy_labels = [h.name.split('(')[0].strip() for h in hostels]
        occupied_data = [h.occupied_beds_count for h in hostels]
        available_data = [h.available_beds_count for h in hostels]

        # 2. Complaint Categories Breakdown
        complaint_counts = db.session.query(
            Complaint.category, func.count(Complaint.id)
        ).group_by(Complaint.category).all()
        
        complaint_map = {cat: 0 for cat in ['electrical', 'plumbing', 'cleanliness', 'internet', 'mess', 'other']}
        for cat, cnt in complaint_counts:
            complaint_map[cat] = cnt

        # 3. Monthly Revenue Trend (Last 6 distinct months or available payment dates)
        fee_records = FeeRecord.query.filter_by(status='paid').order_by(FeeRecord.payment_date.asc()).all()
        month_map = {}
        for f in fee_records:
            m_key = f.payment_date.strftime('%b %Y')
            month_map[m_key] = month_map.get(m_key, 0.0) + float(f.amount)

        if not month_map:
            month_map = {'Current Term': 0.0}

        return {
            'occupancy': {
                'labels': occupancy_labels,
                'occupied': occupied_data,
                'available': available_data
            },
            'complaints': {
                'labels': [k.capitalize() for k in complaint_map.keys()],
                'data': list(complaint_map.values())
            },
            'revenue': {
                'labels': list(month_map.keys()),
                'data': list(month_map.values())
            }
        }

