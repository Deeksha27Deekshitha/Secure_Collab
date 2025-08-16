from django.contrib import admin
from .models import Workspace, WorkspaceUser, WorkspaceInvitation, WorkspaceMembership
# Register your models here.

admin.site.register(Workspace)
admin.site.register(WorkspaceUser)
admin.site.register(WorkspaceInvitation)
admin.site.register(WorkspaceMembership)