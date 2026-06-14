from flask import render_template
from flask import jsonify
from sqlalchemy import func
from app.models.user import User
from app.models.bikelane import BikeLane
from app.models.banner_response import BannerResponse
from . import bp, admin_required

BANNER_BUS_LANES_KEY = 'bus_lanes'


def _get_bus_lanes_banner_stats():
    rows = (
        BannerResponse.query
        .filter_by(banner_key=BANNER_BUS_LANES_KEY)
        .with_entities(BannerResponse.answer, func.count(BannerResponse.id))
        .group_by(BannerResponse.answer)
        .all()
    )
    stats = {'yes': 0, 'no': 0}
    for answer, count in rows:
        if answer in stats:
            stats[answer] = int(count or 0)
    return stats

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
    banner_stats = {
        'bus_lanes': _get_bus_lanes_banner_stats()
    }
    
    return render_template('admin/dashboard.html', stats=stats, banner_stats=banner_stats)


@bp.route('/api/banner/bus-lanes/stats')
@admin_required
def bus_lanes_banner_stats():
    return jsonify(_get_bus_lanes_banner_stats())
