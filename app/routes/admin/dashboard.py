from flask import render_template
from app.models.user import User
from app.models.bikelane import BikeLane
from . import bp, admin_required

@bp.route('/')
@bp.route('/dashboard')
@admin_required
def dashboard():
    """Главная страница админки с статистикой"""
    stats = {
        'total_users': User.query.count(),
        'total_bikelanes': BikeLane.query.count(),
        'pending_bikelanes': BikeLane.query.filter_by(status='pending').count(),
    }
    
    return render_template('admin/dashboard.html', stats=stats)
