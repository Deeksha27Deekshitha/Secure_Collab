from django.urls import path
from .views import custom_login,home,custom_logout,send_signup_link,signup_with_token,forgot_password,reset_password,Get_Started,update_profile,view_profile
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
 
    path('', Get_Started, name='get_started'),
    path('send-signup-link/', send_signup_link, name='send_signup_link'),
    path('signup/<uuid:token>/', signup_with_token, name='signup_with_token'),
    path('login/', custom_login, name='login'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('reset-password/<str:token>/', reset_password, name='reset_password'),
    path('home/', home, name='home'),
    path('profile/', view_profile, name='profile_page'),
    path('update-profile/', update_profile, name='update_profile'),
    path('profile/<str:username>/', view_profile, name='user_profile'),
    path('logout/', custom_logout, name='logout'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
