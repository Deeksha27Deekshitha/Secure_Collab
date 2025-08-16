from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, FileResponse
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import validate_email
from django.contrib.auth import get_user_model
from .models import Workspace, File, Folder, WorkspaceUser, WorkspaceInvitation,DiscussionMessage
from .forms import FileForm, FolderForm, RenameFolderForm, RenameFileForm, EditFileForm
import os
import mimetypes

User = get_user_model()  # Use the custom user model

# Create Workspace
@login_required
def create_workspace(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        visibility = request.POST.get('visibility')

        # Check if all the fields are filled
        if not name or not description or not visibility:
            messages.error(request, "All fields are required.")
            return redirect('workspace:create_workspace')

        # Create a new workspace
        workspace = Workspace(
            name=name,
            description=description,
            visibility=visibility,
            owner=request.user
        )
        workspace.save()

        # Add the creator as a member of the workspace with the 'creator' role
        WorkspaceUser.objects.create(
            workspace=workspace,
            user=request.user,
            role='creator'
        )

        messages.success(request, 'Workspace created successfully!')
        return redirect('workspace:workspace_list')  # Redirect to the workspace list page

    return render(request, 'workspace/create_workspace.html')

from django.shortcuts import render
from .models import Workspace, WorkspaceUser

@login_required
def workspace_list(request):
    # Get workspaces where the user is the owner
    owned_workspaces = Workspace.objects.filter(owner=request.user)

    # Get workspaces where the user is a member (but not the owner)
    joined_workspaces = Workspace.objects.filter(
        workspaceuser__user=request.user
    ).exclude(owner=request.user).distinct()

    # Fetch workspace-user relationships to check roles
    workspace_roles = WorkspaceUser.objects.filter(user=request.user)

    # Add the user's role to each workspace
    for workspace in owned_workspaces:
        workspace.user_role = workspace_roles.filter(workspace=workspace).first().role if workspace_roles.filter(workspace=workspace).exists() else None

    for workspace in joined_workspaces:
        workspace.user_role = workspace_roles.filter(workspace=workspace).first().role if workspace_roles.filter(workspace=workspace).exists() else None

    return render(request, 'workspace/workspace_list.html', {
        'owned_workspaces': owned_workspaces,
        'joined_workspaces': joined_workspaces,
    })


# Toggle Visibility
@login_required
def toggle_visibility(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Ensure only the workspace owner can toggle visibility
    if workspace.owner != request.user:
        messages.error(request, "You do not have permission to modify this workspace.")
        return redirect('workspace:workspace_list')

    if request.method == "POST":
        new_visibility = request.POST.get('visibility')
        if new_visibility in ['public', 'private']:
            workspace.visibility = new_visibility
            workspace.save()
            messages.success(request, f"Workspace visibility changed to {new_visibility}.")
        else:
            messages.error(request, "Invalid visibility option.")
    else:
        messages.error(request, "Invalid request method.")

    return redirect('workspace:workspace_list')


# Workspace Detail
@login_required
def workspace_detail(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    current_folder = None
    folders = Folder.objects.filter(workspace=workspace, parent_folder__isnull=True)  # Root folders
    files = File.objects.filter(workspace=workspace, folder__isnull=True)  # Files at root level

    # If a folder_id is passed, show its content
    folder_id = request.GET.get('folder_id')
    if folder_id:
        current_folder = get_object_or_404(Folder, id=folder_id)
        folders = Folder.objects.filter(workspace=workspace, parent_folder=current_folder)  # Subfolders
        files = File.objects.filter(workspace=workspace, folder=current_folder)  # Files in the current folder

    # Fetch subfolders recursively
    def get_subfolders(folder):
        """Recursively get subfolders and files."""
        subfolders = Folder.objects.filter(parent_folder=folder)
        subfolder_data = []
        for subfolder in subfolders:
            subfolder_data.append({
                'folder': subfolder,
                'files': File.objects.filter(folder=subfolder),
                'subfolders': get_subfolders(subfolder)  # Nested subfolders
            })
        return subfolder_data

    subfolder_data = get_subfolders(current_folder) if current_folder else []  # Hierarchical data for the current folder

    # Determine the user's role in the workspace
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    user_role = workspace_user.role if workspace_user else 'viewer'

    context = {
        'workspace': workspace,
        'current_folder': current_folder,
        'folders': folders,
        'files': files,
        'subfolder_data': subfolder_data,
        'user_role': user_role,  # Pass the user's role to the template
    }

    return render(request, 'workspace/workspace_detail.html', context)


# Invite User
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.validators import validate_email
from .models import Workspace, WorkspaceInvitation

@login_required
def invite_user(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Ensure only the workspace owner or admin can invite users
    if request.user != workspace.owner:
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    if request.method == 'POST':
        email = request.POST.get('email')

        if not email:  # Check if email is empty
            return render(request, 'workspace/invite_user.html', {'workspace': workspace, 'error': 'Email is required.'})

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            return render(request, 'workspace/invite_user.html', {'workspace': workspace, 'error': 'Invalid email format.'})

        # Check if an invitation already exists for this email
        if WorkspaceInvitation.objects.filter(workspace=workspace, email=email).exists():
            return render(request, 'workspace/invite_user.html', {'workspace': workspace, 'error': 'An invitation has already been sent to this email.'})

        # Create the invitation with token
        invitation = WorkspaceInvitation.objects.create(workspace=workspace, email=email)

        # Send invitation email
        invite_url = request.build_absolute_uri(f"/workspace/workspaces/{workspace.id}/join/{invitation.token}/")
        send_mail(
            'Join Workspace Invitation',
            f'You have been invited to join the workspace "{workspace.name}". Click the link to join: {invite_url}',
            'from@example.com',
            [email]
        )

        # Redirect to workspace detail after sending the invitation
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    return render(request, 'workspace/invite_user.html', {'workspace': workspace})


# Join Workspace
@login_required
def join_workspace(request, workspace_id, token):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Check if the user is already a member
    if WorkspaceUser.objects.filter(workspace=workspace, user=request.user).exists():
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    # Check if an invitation exists for this user
    try:
        invitation = WorkspaceInvitation.objects.get(workspace=workspace, token=token, email=request.user.email)
    except ObjectDoesNotExist:
        invitation = None

    # Allow joining if:
    # - The workspace is public OR
    # - The user has a valid invitation
    if workspace.visibility == 'public' or invitation:
        # Add user as a viewer
        WorkspaceUser.objects.create(workspace=workspace, user=request.user, role='viewer')

        # Delete the invitation after successful join (optional)
        if invitation:
            invitation.delete()

        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    # If neither condition is met, raise 404
    raise Http404("You cannot join this private workspace without an invitation.")


# Update User Role
@login_required
def update_user_role(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Ensure only the admin can change user roles
    if request.user != workspace.owner:
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    if request.method == 'POST':
        email = request.POST.get('user_email')
        role = request.POST.get('role')

        user = User.objects.get(email=email)
        workspace_user = WorkspaceUser.objects.get(workspace=workspace, user=user)
        workspace_user.role = role
        workspace_user.save()

        return redirect('workspace:workspace_detail', workspace_id=workspace.id)


# Add Folder
@login_required
def add_folder(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    parent_folder_id = request.GET.get('folder_id')  # Extract folder_id from query string
    parent_folder = None

    if parent_folder_id:
        parent_folder = Folder.objects.filter(id=parent_folder_id).first()

    # Ensure only users with appropriate roles can add folders
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user or workspace_user.role == 'viewer':
        messages.error(request, "You do not have permission to add folders.")
        return redirect('workspace:workspace_detail', workspace_id=workspace_id)

    if request.method == 'POST':
        form = FolderForm(request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.workspace = workspace
            folder.parent_folder = parent_folder  # Assign parent_folder if provided
            folder.save()
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
    else:
        form = FolderForm()

    return render(request, 'workspace/add_folder.html', {
        'form': form,
        'workspace': workspace,
        'parent_folder': parent_folder,
    })

from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Workspace, Folder, WorkspaceUser
from .forms import FileForm

@login_required
def add_file(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    parent_folder_id = request.GET.get('folder_id')  # Get parent folder ID from URL
    parent_folder = None  # Default to None (root workspace)

    if parent_folder_id:
        parent_folder = Folder.objects.filter(id=parent_folder_id).first()

    # Ensure that a folder exists before uploading a file
    if parent_folder is None:
        messages.error(request, "You need to create and be in a folder first before uploading a file.")
        return redirect('workspace:workspace_detail', workspace_id=workspace_id)

    if request.method == 'POST':
        form = FileForm(request.POST, request.FILES)
        if form.is_valid():
            file_instance = form.save(commit=False)
            file_instance.workspace = workspace
            file_instance.folder = parent_folder  # Assign parent_folder (ensured to exist)
            file_instance.uploaded_by = request.user
            file_instance.save()
            messages.success(request, "File has been uploaded successfully.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)

    else:
        form = FileForm()

    return render(request, 'workspace/add_file.html', {
        'form': form,
        'workspace': workspace,
        'parent_folder': parent_folder,
    })

# Delete File
@login_required
def delete_file(request, file_id):
    file_instance = get_object_or_404(File, id=file_id)
    workspace = file_instance.workspace

    # Ensure only users with appropriate roles can delete files
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user or workspace_user.role == 'viewer':
        messages.error(request, "You do not have permission to delete files.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    if request.method == "POST":
        file_instance.delete()
        messages.success(request, "File has been deleted.")
    return redirect('workspace:workspace_detail', workspace_id=workspace.id)


# Delete Folder
@login_required
def delete_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id)
    workspace = folder.workspace

    # Ensure only users with appropriate roles can delete folders
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user or workspace_user.role == 'viewer':
        messages.error(request, "You do not have permission to delete folders.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    if request.method == "POST":
        # Delete all files in this folder
        File.objects.filter(folder=folder).delete()

        # Recursively delete all subfolders
        Folder.objects.filter(parent_folder=folder).delete()

        # Delete the folder itself
        folder.delete()

        messages.success(request, "Folder and all its contents have been deleted.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    return render(request, 'workspace/confirm_delete_folder.html', {'folder': folder})


# Edit Folder
@login_required
def edit_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id)
    workspace = folder.workspace

    # Ensure only users with appropriate roles can edit folders
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user or workspace_user.role == 'viewer':
        messages.error(request, "You do not have permission to edit folders.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    if request.method == 'POST':
        form = RenameFolderForm(request.POST, instance=folder)
        if form.is_valid():
            form.save()
            return redirect('workspace:workspace_detail', workspace_id=workspace.id)
    else:
        form = RenameFolderForm(instance=folder)

    return render(request, 'workspace/edit_folder.html', {'form': form, 'folder': folder})


# Edit File
@login_required
def edit_file(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    workspace = file_obj.workspace

    # Ensure only users with appropriate roles can edit files
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user or workspace_user.role == 'viewer':
        messages.error(request, "You do not have permission to edit files.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    # Get the file extension
    file_extension = os.path.splitext(file_obj.file.name)[1].lower()

    # Check if the file extension is editable
    EDITABLE_EXTENSIONS = ['.txt', '.md', '.json', '.html', '.css', '.js', '.py']
    if file_extension in EDITABLE_EXTENSIONS:
        # Read the current content of the file
        file_path = file_obj.file.path
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        # Handle form submission for editing
        if request.method == "POST":
            form = EditFileForm(request.POST)
            if form.is_valid():
                # Save the edited content back to the file
                new_content = form.cleaned_data["content"]
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                # Update the file's modified timestamp
                file_obj.save()

                # Provide a success message and redirect
                messages.success(request, "File updated successfully!")
                return redirect('workspace:workspace_detail', workspace_id=workspace.id)
        else:
            # Display the file's content in the form for editing
            form = EditFileForm(initial={'content': file_content})

        return render(request, 'workspace/edit_file.html', {
            'form': form,
            'file_obj': file_obj
        })

    # If the file is not editable, show an error
    messages.error(request, "This file type is not supported for editing.")
    return redirect('workspace:workspace_detail', workspace_id=workspace.id)


# Rename File
@login_required
def rename_file(request, file_id):
    file = get_object_or_404(File, id=file_id)
    workspace = file.workspace

    # Ensure only users with appropriate roles can rename files
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user or workspace_user.role == 'viewer':
        messages.error(request, "You do not have permission to rename files.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    if request.method == 'POST':
        form = RenameFileForm(request.POST, instance=file)
        if form.is_valid():
            form.save()
            return redirect('workspace:workspace_detail', workspace_id=workspace.id)
    else:
        form = RenameFileForm(instance=file)

    return render(request, 'workspace/rename_file.html', {'form': form, 'file': file})


# Rename Folder
@login_required
def rename_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id)
    workspace = folder.workspace

    # Ensure only users with appropriate roles can rename folders
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user or workspace_user.role == 'viewer':
        messages.error(request, "You do not have permission to rename folders.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    if request.method == 'POST':
        form = RenameFolderForm(request.POST, instance=folder)
        if form.is_valid():
            form.save()
            return redirect('workspace:workspace_detail', workspace_id=workspace.id)
    else:
        form = RenameFolderForm(instance=folder)

    return render(request, 'workspace/rename_folder.html', {'form': form, 'folder': folder})


# Download File
@login_required
def download_file(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    file_path = file_obj.file.path
    file_name = os.path.basename(file_path)

    with open(file_path, 'rb') as file:
        response = HttpResponse(file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response


# View Text File
@login_required
def view_text_file(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    workspace = file_obj.workspace  # Ensure workspace exists

    # Ensure the file belongs to a workspace
    if not workspace or not workspace.id:
        messages.error(request, "This file is not linked to any workspace.")
        return redirect('workspace:workspace_list')  # Redirect to a general list of workspaces

    # Ensure only users with appropriate roles can view files
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user:
        messages.error(request, "You do not have permission to view this file.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)

    # Get the file extension
    file_extension = os.path.splitext(file_obj.file.name)[1].lower()

    # Check if the file extension is readable
    READABLE_EXTENSIONS = ['.txt', '.md', '.json', '.html', '.css', '.js', '.py']
    if file_extension in READABLE_EXTENSIONS:
        try:
            # Read the file content
            file_path = file_obj.file.path
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            print("Error reading file:", e)
            return HttpResponse("Error reading file.", status=500)

        return render(request, 'workspace/view_text_file.html', {
            'file_obj': file_obj,
            'file_content': file_content
        })

    # If the file is not readable, show an error
    messages.error(request, "This file type cannot be displayed as text.")
    return redirect('workspace:workspace_detail', workspace_id=workspace.id)



def view_image(request, file_id):
    # Get the file object from the database
    file_obj = get_object_or_404(File, id=file_id)
    
    # Ensure the file is an image (can be further optimized with a file extension check)
    mime_type, encoding = mimetypes.guess_type(file_obj.file.name)
    if mime_type and mime_type.startswith('image'):
        return render(request, 'workspace/view_image.html', {
            'file_obj': file_obj
        })
    
    # If the file is not an image, show an error
    messages.error(request, "File is not a valid image.")
    return redirect('workspace:workspace_detail', workspace_id=file_obj.workspace.id)


from django.shortcuts import render, get_object_or_404, redirect
from .models import Workspace, WorkspaceUser
from django.contrib.auth.decorators import login_required

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Workspace, WorkspaceUser
@login_required
def view_members(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    members = WorkspaceUser.objects.filter(workspace=workspace)

    # Check if the current user is the creator or an editor
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    is_creator_or_editor = workspace_user and workspace_user.role in ['creator', 'editor']

    if request.method == "POST" and is_creator_or_editor:
        action = request.POST.get('action')  # Check which form was submitted

        # Change role action
        if action == 'change_role' and 'user_id' in request.POST and 'new_role' in request.POST:
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('new_role')

            # Ensure the new role is valid
            if new_role in ['creator', 'editor', 'viewer']:
                try:
                    member = WorkspaceUser.objects.get(id=user_id, workspace=workspace)
                    member.role = new_role
                    member.save()
                    messages.success(request, f"Role of {member.user.username} has been updated to {new_role}.")
                except WorkspaceUser.DoesNotExist:
                    messages.error(request, "User not found in the workspace.")

        # Remove user action
        elif action == 'remove_user' and 'remove_user_id' in request.POST:
            user_id = request.POST.get('remove_user_id')
            print(f"Attempting to remove user with ID: {user_id}")  # Debugging

            try:
                member_to_remove = WorkspaceUser.objects.get(id=user_id, workspace=workspace)
                print(f"Found user to remove: {member_to_remove.user.username}")  # Debugging
                member_to_remove.delete()
                messages.success(request, f"{member_to_remove.user.username} has been removed from the workspace.")
            except WorkspaceUser.DoesNotExist:
                messages.error(request, "User not found in the workspace.")

        # Redirect to avoid resubmission on refresh
        return redirect('workspace:view_members', workspace_id=workspace.id)

    context = {
        'workspace': workspace,
        'members': members,
        'is_creator_or_editor': is_creator_or_editor,
    }

    return render(request, 'workspace/view_members.html', context)


@login_required
def manage_workspace_members(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()

    if not workspace_user:
        messages.error(request, "You are not a member of this workspace.")
        return redirect('home')

    if workspace_user.role not in ['creator', 'editor']:
        messages.error(request, "You are not authorized to manage roles in this workspace.")
        return redirect('workspace_detail', workspace_id=workspace_id)

    members = WorkspaceUser.objects.filter(workspace=workspace)

    if request.method == 'POST':
        action = request.POST.get('action')  # Check which form was submitted

        if action == 'change_role':  # Role change logic
            print("Attempting to change role")  # Debugging
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('new_role')

            if new_role not in ['creator', 'editor', 'viewer']:
                messages.error(request, "Invalid role selected.")
                return redirect('workspace_members', workspace_id=workspace_id)

            try:
                user_to_update = WorkspaceUser.objects.get(id=user_id, workspace=workspace)
            except WorkspaceUser.DoesNotExist:
                messages.error(request, "User not found in the workspace.")
                return redirect('workspace_members', workspace_id=workspace_id)

            if user_to_update.role == 'creator':
                messages.error(request, "You cannot change the role of the creator.")
                return redirect('workspace_members', workspace_id=workspace_id)

            user_to_update.role = new_role
            user_to_update.save()
            messages.success(request, f"Role of {user_to_update.user.username} has been updated to {new_role}.")
            return redirect('workspace_members', workspace_id=workspace_id)

        elif action == 'remove_user':  # Remove user logic
            remove_user_id = request.POST.get('remove_user')
            print(f"Attempting to remove user with ID: {remove_user_id}")  # Debugging

            try:
                user_to_remove = WorkspaceUser.objects.get(id=remove_user_id, workspace=workspace)
                print(f"Found user to remove: {user_to_remove.user.username}")  # Debugging
            except WorkspaceUser.DoesNotExist:
                messages.error(request, "User not found in the workspace.")
                return redirect('workspace_members', workspace_id=workspace_id)

            if user_to_remove.role == 'creator':
                messages.error(request, "The creator cannot be removed from the workspace.")
                return redirect('workspace_members', workspace_id=workspace_id)

            user_to_remove.delete()
            messages.success(request, f"{user_to_remove.user.username} has been removed from the workspace.")
            return redirect('workspace_members', workspace_id=workspace_id)

    return render(request, 'workspace/manage_members.html', {
        'workspace': workspace,
        'members': members,
        'is_creator_or_editor': workspace_user.role in ['creator', 'editor'],  # Pass this to the template
    })

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Workspace, WorkspaceUser

@login_required
def search_workspaces(request):
    query = request.GET.get('q')  # Get the search query from the URL
    public_workspaces = None  # Set to None initially

    if query:
        # Filter only public workspaces matching the search query
        public_workspaces = Workspace.objects.filter(
            visibility='public'
        ).filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

        # Exclude workspaces the user is already a member of
        user_workspaces = WorkspaceUser.objects.filter(user=request.user).values_list('workspace_id', flat=True)
        public_workspaces = public_workspaces.exclude(id__in=user_workspaces)

    return render(request, 'workspace/search_workspaces.html', {
        'public_workspaces': public_workspaces,  # Will be None if no query
        'query': query,
    })


@login_required
def join_workspace_public(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Ensure the workspace is public
    if workspace.visibility != 'public':
        messages.error(request, "You cannot join a private workspace.")
        return redirect('workspace:search_workspaces')

    # Check if the user is already a member of the workspace
    if WorkspaceUser.objects.filter(workspace=workspace, user=request.user).exists():
        messages.warning(request, "You are already a member of this workspace.")
        return redirect('workspace:search_workspaces')

    # Add the user to the workspace as a viewer
    WorkspaceUser.objects.create(
        workspace=workspace,
        user=request.user,
        role='viewer'
    )

    messages.success(request, f"You have successfully joined the workspace: {workspace.name}.")
    return redirect('workspace:workspace_detail', workspace_id=workspace.id)



from django.contrib import messages

@login_required
def delete_workspace(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Ensure only the owner can delete the workspace
    if workspace.owner != request.user:
        messages.error(request, "You do not have permission to delete this workspace.")
        return redirect('workspace:workspace_list')

    # Delete the workspace
    workspace.delete()
    messages.success(request, f"Workspace '{workspace.name}' has been deleted.")

    return redirect('workspace:workspace_list')



@login_required
def add_message(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    
    # Check user role
    workspace_user = WorkspaceUser.objects.filter(workspace=workspace, user=request.user).first()
    if not workspace_user or workspace_user.role == 'viewer':
        messages.error(request, "You don't have permission to post messages in this workspace.")
        return redirect('workspace:workspace_detail', workspace_id=workspace_id)
    
    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        if message_text:
            DiscussionMessage.objects.create(
                workspace=workspace,
                user=request.user,
                message=message_text
            )
            messages.success(request, "Message posted successfully!")
        else:
            messages.error(request, "Message cannot be empty.")
    
    return redirect('workspace:workspace_detail', workspace_id=workspace_id)

@login_required
def delete_message(request, message_id):
    message = get_object_or_404(DiscussionMessage, id=message_id)
    
    # Check if user is the message author or workspace owner/admin
    if request.user != message.user and request.user != message.workspace.owner:
        messages.error(request, "You don't have permission to delete this message.")
        return redirect('workspace:workspace_detail', workspace_id=message.workspace.id)
    
    message.delete()
    messages.success(request, "Message deleted successfully!")
    return redirect('workspace:workspace_detail', workspace_id=message.workspace.id)



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import Workspace, WorkspaceUser
from .forms import SellWorkspaceForm
import razorpay
import json
from django.http import JsonResponse, HttpResponseBadRequest

# Initialize Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@login_required
def sell_workspace(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    
    if request.user != workspace.owner:
        messages.error(request, "Only the workspace owner can sell this workspace.")
        return redirect('workspace:workspace_detail', workspace_id=workspace.id)
    
    if request.method == 'POST':
        form = SellWorkspaceForm(request.POST, instance=workspace)
        if form.is_valid():
            workspace = form.save(commit=False)
            if workspace.is_for_sale:
                workspace.sale_creator = request.user
                messages.success(request, f"Workspace is now for sale for ₹{workspace.sale_price}")
            else:
                workspace.sale_price = None
                messages.success(request, "Workspace is no longer for sale")
            workspace.save()
            return redirect('workspace:workspace_detail', workspace_id=workspace.id)
    else:
        form = SellWorkspaceForm(instance=workspace)
    
    return render(request, 'workspace/sell_workspace.html', {
        'form': form,
        'workspace': workspace
    })
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import razorpay
from django.conf import settings

# Initialize Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
# workspace/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
import razorpay
from django.conf import settings
import json
from .models import Workspace
# workspace/views.py
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
import razorpay
from django.conf import settings
from .models import Workspace
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

@require_POST
@login_required
def initiate_payment(request, workspace_id):
    try:
        # Debug: Log the start of the request
        logger.info(f"Initiate payment request for workspace {workspace_id} from user {request.user.id}")

        # 1. Verify Razorpay configuration
        if not all([hasattr(settings, 'RAZORPAY_KEY_ID'), 
                   hasattr(settings, 'RAZORPAY_KEY_SECRET')]):
            logger.error("Razorpay credentials not configured")
            return JsonResponse({
                'success': False,
                'error': 'Payment gateway not configured'
            }, status=500)

        # 2. Initialize Razorpay client
        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        except Exception as e:
            logger.error(f"Razorpay client initialization failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Payment gateway error'
            }, status=500)

        # 3. Get workspace with detailed error handling
        try:
            workspace = Workspace.objects.get(id=workspace_id)
        except Workspace.DoesNotExist:
            logger.error(f"Workspace {workspace_id} not found")
            return JsonResponse({
                'success': False,
                'error': 'Workspace not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error fetching workspace: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Error accessing workspace'
            }, status=500)

        # 4. Validate sale conditions
        if not workspace.is_for_sale:
            logger.error(f"Workspace {workspace_id} is not for sale")
            return JsonResponse({
                'success': False,
                'error': 'This workspace is not for sale'
            }, status=400)

        if request.user == workspace.owner:
            logger.error(f"User {request.user.id} tried to buy their own workspace")
            return JsonResponse({
                'success': False,
                'error': 'You cannot buy your own workspace'
            }, status=400)

        # 5. Validate and convert price
        try:
            sale_price = float(workspace.sale_price)
            amount = int(sale_price * 100)  # Convert to paise
            if amount < 10000:  # Minimum ₹100
                logger.error(f"Invalid price {workspace.sale_price} for workspace {workspace_id}")
                return JsonResponse({
                    'success': False,
                    'error': 'Minimum sale price is ₹100'
                }, status=400)
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid price format {workspace.sale_price}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid sale price format'
            }, status=400)

        # 6. Create Razorpay order with error handling
        try:
            order = client.order.create({
                'amount': amount,
                'currency': 'INR',
                'receipt': f'workspace_{workspace.id}',
                'payment_capture': 1
            })
            logger.info(f"Created Razorpay order {order['id']} for workspace {workspace_id}")
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Payment processing error'
            }, status=500)

        return JsonResponse({
            'success': True,
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency'],
            'key_id': settings.RAZORPAY_KEY_ID,
            'workspace_id': workspace.id,
            'buyer_id': request.user.id
        })

    except Exception as e:
        logger.error(f"Unexpected error in initiate_payment: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred'
        }, status=500)
    

@csrf_exempt
def verify_payment(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_signature = data.get('razorpay_signature')
            workspace_id = data.get('workspace_id')
            buyer_id = data.get('buyer_id')
            
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            
            client.utility.verify_payment_signature(params_dict)
            
            # Get workspace and buyer
            workspace = Workspace.objects.get(id=workspace_id)
            buyer = User.objects.get(id=buyer_id)
            
            # Remove ALL existing users from workspace
            WorkspaceUser.objects.filter(workspace=workspace).delete()
            
            # Transfer ownership
            workspace.owner = buyer
            workspace.is_for_sale = False
            workspace.sale_price = None
            workspace.save()
            
            # Add buyer as the only member with creator role
            WorkspaceUser.objects.create(
                workspace=workspace,
                user=buyer,
                role='creator'
            )
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)