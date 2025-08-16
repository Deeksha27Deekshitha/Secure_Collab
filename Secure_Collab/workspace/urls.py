# workspace/urls.py

from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'workspace'  # This is where you define the namespace

urlpatterns = [
    path('create/', views.create_workspace, name='create_workspace'),
    path('workspace/list/', views.workspace_list, name='workspace_list'),
    path('workspace/toggle-visibility/<int:workspace_id>/', views.toggle_visibility, name='toggle_visibility'),

    path('workspaces/<int:workspace_id>/add-folder/', views.add_folder, name='add_folder'),
    path('workspaces/<int:workspace_id>/add-file/', views.add_file, name='add_file'),
   
    # path('toggle-visibility/<int:workspace_id>/', views.toggle_visibility, name='toggle_visibility'),
    path('workspaces/<int:workspace_id>/', views.workspace_detail, name='workspace_detail'),
    path('workspaces/folders/<int:folder_id>/delete/', views.delete_folder, name='delete_folder'),
    path('workspaces/files/<int:file_id>/delete/', views.delete_file, name='delete_file'),
     path('workspaces/folders/<int:folder_id>/rename/', views.rename_folder, name='rename_folder'),
    path('workspaces/files/<int:file_id>/rename/', views.rename_file, name='rename_file'),

    path('workspaces/folders/<int:folder_id>/edit/', views.edit_folder, name='edit_folder'),
    path('workspaces/files/<int:file_id>/edit/', views.edit_file, name='edit_file'),
    path('file/edit/<int:file_id>/', views.edit_file, name='edit_file'),
  
     path('file/delete/<int:file_id>/', views.delete_file, name='delete_file'),
    path('file/download/<int:file_id>/', views.download_file, name='download_file'),
    path('file/view/<int:file_id>/', views.view_image, name='view_image'),
    # path('workspaces/<int:workspace_id>/create-folder/', views.create_folder, name='create_folder'),
    # path('workspaces/<int:workspace_id>/add-file/', views.add_file, name='add_file'),
    # path('workspaces/files/<int:file_id>/edit/', views.edit_file, name='edit_file'),
 
    # Add other workspace URLs here
    path('<int:workspace_id>/invite/', views.invite_user, name='invite_user'),
    path('workspaces/<int:workspace_id>/join/<uuid:token>/', views.join_workspace, name='join_workspace'),
    path('workspaces/files/<int:file_id>/view/', views.view_text_file, name='view_file'),
    path('workspace/<int:workspace_id>/members/', views.view_members, name='view_members'),
    path('workspace/<int:workspace_id>/members/', views.manage_workspace_members, name='workspace_members'),

    path('workspaces/search/', views.search_workspaces, name='search_workspaces'),
    
    # Join a public workspace
    path('join/<int:workspace_id>/', views.join_workspace_public, name='join_workspace_public'),
    path('delete/<int:workspace_id>/', views.delete_workspace, name='delete_workspace'),


    path('workspaces/<int:workspace_id>/add-message/', views.add_message, name='add_message'),
    path('workspaces/messages/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('workspaces/<int:workspace_id>/sell/', views.sell_workspace, name='sell_workspace'),

    path('workspaces/<int:workspace_id>/initiate-payment/', views.initiate_payment, name='initiate_payment'),
    path('api/verify-payment/', views.verify_payment, name='verify_payment'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)