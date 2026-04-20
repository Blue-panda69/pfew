from django.urls import path
from . import views

app_name = 'core'

admin_report_patterns = [
    path('campaign-report/<int:campaign_id>/', views.campaign_report_view, name='admin_campaign_report'),
    path('campaign-report-data/<int:campaign_id>/', views.campaign_report_data, name='admin_campaign_report_data'),
]

urlpatterns = [
    path('track/pixel/<uuid:tracking_id>/', views.track_pixel, name='track_pixel'),
    path('track/click/<uuid:token>/', views.track_click, name='track_click'),   # token, not tracking_id
    path('landing-page/<slug:slug>/', views.landing_page_view, name='landing_page'),
    path('landing-page/<slug:slug>/submit/', views.landing_page_form_submit, name='landing_page_submit'),
]