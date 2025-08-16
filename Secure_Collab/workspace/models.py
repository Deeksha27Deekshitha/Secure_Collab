from django.db import models
from django.conf import settings  # Import settings for the custom user model
from cryptography.fernet import Fernet
from django.core.files.base import ContentFile
from django.utils.timezone import now
from datetime import timedelta
import uuid

from django.contrib.auth import get_user_model


# Now you can use User to access the CustomUser model
User = get_user_model()

# Workspace Model
class Workspace(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    visibility = models.CharField(max_length=20, choices=[('private', 'Private'), ('public', 'Public')])
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='owned_workspaces', on_delete=models.CASCADE)
    is_for_sale = models.BooleanField(default=False)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sale_creator = models.ForeignKey(settings.AUTH_USER_MODEL, 
                                   on_delete=models.SET_NULL, 
                                   null=True, 
                                   blank=True,
                                   related_name='workspaces_for_sale')

    def __str__(self):
        return self.name


# WorkspaceUser Model
class WorkspaceUser(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[('viewer', 'Viewer'), ('editor', 'Editor'), ('creator', 'Creator')], default='viewer')

    def __str__(self):
        return f"{self.user.username} in {self.workspace.name}"

# WorkspaceInvitation Model
class WorkspaceInvitation(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite for {self.email} to {self.workspace.name}"


# WorkspaceMembership Model
class WorkspaceMembership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='workspace_memberships')
    is_admin = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} in {self.workspace.name}"


# Invitation Model
# class Invitation(models.Model):
#     email = models.EmailField()
#     workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='invitations')
#     token = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
#     is_accepted = models.BooleanField(default=False)
#     sent_at = models.DateTimeField(auto_now_add=True)
#     expires_at = models.DateTimeField()

#     def save(self, *args, **kwargs):
#         if not self.expires_at:
#             self.expires_at = now() + timedelta(days=7)
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"Invitation to {self.email} for {self.workspace.name}"


# Folder Model
class Folder(models.Model):
    name = models.CharField(max_length=100)
    parent_folder = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subfolders')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='folders')
    created_at = models.DateTimeField(auto_now_add=True)

    def get_hierarchy(self):
        hierarchy = [self]
        if self.parent_folder:
            hierarchy = self.parent_folder.get_hierarchy() + hierarchy
        return hierarchy

    def get_root_folder(self):
        if self.parent_folder:
            return self.parent_folder.get_root_folder()
        return self

    def __str__(self):
        return f"Folder: {self.name} in Workspace: {self.workspace.name}"

    @classmethod
    def get_root_folders(cls, workspace):
        return cls.objects.filter(workspace=workspace, parent_folder__isnull=True)


# File Model
class File(models.Model):
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to='workspace_files/')
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_editable = models.BooleanField(default=False)

    def __str__(self):
        return f"File: {self.name} in Workspace: {self.workspace.name}"

    def get_file_extension(self):
        return self.name.split('.')[-1].lower()


# File Log Model
class FileLog(models.Model):
    ACTION_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('edited', 'Edited'),
        ('deleted', 'Deleted'),
    ]

    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.user.username} {self.get_action_display()} {self.file.name} on {self.timestamp}"


# File Upload Model with Encryption
class FileUpload(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='file_uploads')
    file_path = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    file = models.FileField(upload_to='workspace_files/')
    encrypted_file = models.FileField(upload_to='encrypted_files/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} uploaded to {self.workspace.name} by {self.uploaded_by.email}"

    def save(self, *args, **kwargs):
        if self.file and not self.encrypted_file:
            self.encrypt_file()
        super().save(*args, **kwargs)

    def encrypt_file(self):
        key = Fernet.generate_key()
        cipher = Fernet(key)

        # Encrypt file content
        file_content = self.file.read()
        encrypted_content = cipher.encrypt(file_content)

        # Save encrypted content to Django FileField
        encrypted_file = ContentFile(encrypted_content)
        self.encrypted_file.save(f"encrypted_{self.file_name}", encrypted_file, save=False)



# Discussion Message Model
class DiscussionMessage(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Message by {self.user.username} in {self.workspace.name}"