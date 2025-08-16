from django.core.mail import send_mail
from django.conf import settings
from .models import EmailVerification, CustomUser
from django.utils.timezone import now
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.timezone import now, timedelta

def send_signup_link(request):
    if request.method == 'POST':
        email = request.POST['email']

        # Check if the email already exists
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists. Please log in.')
            return redirect('login')

        # Generate or get the token entry, updating the created_at timestamp
        token_entry, created = EmailVerification.objects.update_or_create(
            email=email,
            defaults={
                'is_verified': False,
                'created_at': now()  # Explicitly set the creation time
            }
        )

        # Send email with the signup link
        signup_url = f"http://127.0.0.1:8000/users/signup/{token_entry.token}/"
        send_mail(
            subject="Complete Your Signup",
            message=f"Click the link below to complete your signup:\n{signup_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        messages.success(request, 'Signup link has been sent to your email.')
        return redirect('send_signup_link')

    return render(request, 'users/send_signup_link.html')

def signup_with_token(request, token):
    try:
        token_entry = EmailVerification.objects.get(token=token)

        # Check if token is used or expired (24 hours)
        if token_entry.is_verified:
            messages.error(request, 'This signup link has already been used.')
            return redirect('send_signup_link')
            
        # More accurate expiration check (using total_seconds)
        expiration_time = token_entry.created_at + timedelta(days=1)
        if now() > expiration_time:
            messages.error(request, 'The signup link has expired. Please request a new one.')
            return redirect('send_signup_link')

        if request.method == 'POST':
            username = request.POST['username']
            dob = request.POST['dob']
            phone_number = request.POST['phone_number']
            password = request.POST['password']
            confirm_password = request.POST['confirm_password']

            if password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return redirect('signup_with_token', token=token)

            if CustomUser.objects.filter(phone_number=phone_number).exists():
                messages.error(request, 'Phone number already exists. Please use a different one.')
                return redirect('signup_with_token', token=token)

            if CustomUser.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists. Please choose another.')
                return redirect('signup_with_token', token=token)

            user = CustomUser.objects.create_user(
                email=token_entry.email,
                username=username,
                dob=dob,
                phone_number=phone_number,
                password=password
            )

            token_entry.is_verified = True
            token_entry.save()

            messages.success(request, 'Account created successfully! You can now log in.')
            return redirect('login')

        return render(request, 'users/signup_with_token.html', {'email': token_entry.email})

    except EmailVerification.DoesNotExist:
        messages.error(request, 'Invalid signup link.')
        return redirect('send_signup_link')


from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

def custom_login(request):
    if request.user.is_authenticated:
        return redirect('home')  # Redirect to home page if user is already logged in

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Authenticate the user using email and password
        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')  # Redirect to a page after successful login
        else:
            messages.error(request, "Invalid email or password.")
    
    return render(request, 'users/login.html')


from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from django.utils.crypto import get_random_string
from .models import PasswordResetToken, CustomUser
import logging

# Configure logging for debugging
logger = logging.getLogger(__name__)

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        # Check if email exists in the system
        if not CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email does not exist.')
            return redirect('forgot_password')
        
        # Delete any existing token for the email to prevent duplicates
        PasswordResetToken.objects.filter(email=email).delete()
        
        # Generate a new token
        new_token = get_random_string(32)
        PasswordResetToken.objects.create(email=email, token=new_token)
        
        # Construct the reset URL
        reset_url = f"http://127.0.0.1:8000/users/reset-password/{new_token}/"
        
        try:
            send_mail(
                subject="Reset Your Password",
                message=f"Click the link below to reset your password:\n{reset_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            messages.success(request, 'Password reset link has been sent to your email.')
        except Exception as e:
            logger.error(f"Error sending password reset email: {e}")
            messages.error(request, 'Failed to send email. Please try again later.')
        
        return redirect('forgot_password')
    
    return render(request, 'users/forgot_password.html')


from django.contrib.auth.hashers import make_password
from django.utils.timezone import now
from .models import PasswordResetToken, CustomUser
from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from .models import PasswordResetToken, CustomUser

def reset_password(request, token):
    try:
        # Get the token entry
        token_entry = PasswordResetToken.objects.get(token=token)

        # Check if token is valid
        if not token_entry.is_valid():
            messages.error(request, 'The token has expired or is invalid.')
            return redirect('forgot_password')

        if request.method == 'POST':
            new_password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')

            # Validate passwords
            if not new_password or not confirm_password:
                messages.error(request, 'Password fields cannot be empty.')
                return redirect(f'/reset-password/{token}/')

            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return redirect(f'/reset-password/{token}/')

            # Update the user's password
            user = CustomUser.objects.get(email=token_entry.email)
            user.password = make_password(new_password)
            user.save()

            # Delete the token after successful reset
            token_entry.delete()

            messages.success(request, 'Password reset successfully.')
            return redirect('login')

        # Render the reset password form
        return render(request, 'users/reset_password.html', {'token': token})

    except PasswordResetToken.DoesNotExist:
        # Handle invalid token
        messages.error(request, 'Invalid token.')
        return redirect('forgot_password')



from django.shortcuts import render, redirect
from django.contrib.auth import logout

def home(request):
    if not request.user.is_authenticated:
        return redirect('login')  # Redirect to login if user is not authenticated

    return render(request, 'users/home.html', {'username': request.user.username})

def custom_logout(request):
    logout(request)  # This will log out the user
    return redirect('login')  # Redirect to login page after logging out


def Get_Started(request):
    return render(request, 'users/index.html') 

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Profile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Profile
from django.contrib.auth import get_user_model

User = get_user_model()  # This will get your custom user model

@login_required
def view_profile(request, username=None):
    if username is None:
        username = request.user.username
    
    # Get the custom user object
    user = get_object_or_404(User, username=username)
    
    # Get or create the profile
    profile, created = Profile.objects.get_or_create(user=user)
    
    context = {
        'profile': profile,
        'is_own_profile': request.user.username == username,
        'profile_created': created
    }
    return render(request, 'users/profile_view.html', context)


@login_required
def update_profile(request):
    # Get or create the profile for the logged-in user
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        bio = request.POST.get('bio', '')
        profile_image = request.FILES.get('profile_image')
        remove_image = request.POST.get('remove_image')

        # Update the profile fields
        if bio:
            profile.bio = bio
        if profile_image:
            profile.profile_image = profile_image
        elif remove_image:
            profile.profile_image = None

        profile.save()
        return redirect('user_profile', username=request.user.username)

    return render(request, 'users/profile_update.html', {'profile': profile})