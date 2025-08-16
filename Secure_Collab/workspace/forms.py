from django import forms
from .models import Folder, File
from .models import Workspace

class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['name'] 

class FileForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['name', 'file']

class FileEditForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['name']
from django import forms
from .models import Folder, File

class RenameFolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['name']

class RenameFileForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['name']

class EditFileForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea(attrs={'rows': 20, 'cols': 80}))

class InviteUserForm(forms.Form):
    email = forms.EmailField(label='Invite Email', required=True)


class SellWorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ['is_for_sale', 'sale_price']
        widgets = {
            'sale_price': forms.NumberInput(attrs={
                'min': '100',
                'step': '100',
                'placeholder': 'Enter price in INR'
            })
        }