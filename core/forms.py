from django import forms
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.utils.safestring import mark_safe
from .models import CampaignTarget, Campaign, Target, EmailTemplate, LandingPage, SmtpAccount

class TargetTableWidget(forms.CheckboxSelectMultiple):
    template_name = 'admin/widgets/target_table.html'
    option_template_name = 'admin/widgets/target_table_option.html'

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        target_obj = label if hasattr(label, 'email') else None
        option['target_data'] = {
            'email': getattr(target_obj, 'email', ''),
            'first_name': getattr(target_obj, 'first_name', ''),
            'last_name': getattr(target_obj, 'last_name', ''),
            'department': getattr(target_obj, 'department', ''),
            'groups': getattr(target_obj, 'groups', ''),
        }
        option['label'] = str(label)
        return option

class TargetChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj

class CampaignForm(forms.ModelForm):
    sender_account = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=True,
        label='Compte d\'envoi',
        help_text='Sélectionnez le compte Gmail actif qui enverra cette campagne.',
        empty_label='---------'
    )
    email_template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.all(),
        required=False,
        label='Email template',
        help_text='Template used automatically when the campaign starts.'
    )
    landing_page = forms.ModelChoiceField(
        queryset=LandingPage.objects.all(),
        required=False,
        label='Landing page',
        help_text='Landing page associated with this campaign.'
    )
    targets = TargetChoiceField(
        queryset=Target.objects.all(),
        required=False,
        widget=TargetTableWidget(attrs={'class': 'target-table-widget'}),
        label='Targets for this campaign',
        help_text='Choose one or more targets for this campaign.'
    )

    class Meta:
        model = Campaign
        fields = ['name', 'description', 'sender_account', 'email_template', 'landing_page', 'start_date', 'end_date', 'status', 'targets']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide sender accounts already used by active campaigns (draft/running).
        active_campaigns = Campaign.objects.filter(status__in=['draft', 'running'])
        if self.instance and self.instance.pk:
            active_campaigns = active_campaigns.exclude(pk=self.instance.pk)
        blocked_sender_ids = active_campaigns.values_list('sender_account_id', flat=True)
        self.fields['sender_account'].queryset = SmtpAccount.objects.filter(is_active=True).exclude(
            id__in=blocked_sender_ids
        )
        
        if self.instance and self.instance.pk:
            self.fields['targets'].initial = Target.objects.filter(campaigntarget__campaign=self.instance)
            if self.instance.sender_account_id:
                # Keep currently selected sender visible on edit even if inactive/blocked.
                self.fields['sender_account'].queryset = SmtpAccount.objects.filter(
                    (Q(is_active=True) & ~Q(id__in=blocked_sender_ids)) | Q(pk=self.instance.sender_account_id)
                )

        if not self.fields['sender_account'].queryset.exists():
            self.fields['sender_account'].help_text += ' Veuillez ajouter au moins un compte d\'envoi actif avant de sauvegarder cette campagne.'

    def clean_sender_account(self):
        sender_account = self.cleaned_data.get('sender_account')
        if not sender_account:
            raise forms.ValidationError('Un compte d\'envoi est requis. Veuillez sélectionner un compte Gmail actif pour cette campagne.')
        return sender_account

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            return name
        duplicate_qs = Campaign.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
        if duplicate_qs.exists():
            raise forms.ValidationError('A campaign with this name already exists. Please choose a different name.')
        return name

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date:
            min_start = timezone.now() + timedelta(minutes=1)
            if start_date < min_start:
                cleaned_data['start_date'] = min_start

        if end_date and cleaned_data.get('start_date'):
            min_end = cleaned_data['start_date'] + timedelta(minutes=5)
            if end_date < min_end:
                cleaned_data['end_date'] = min_end

        return cleaned_data


class SmtpAccountForm(forms.ModelForm):
    email = forms.EmailField(
        label='Adresse Gmail',
        help_text='Votre adresse Gmail (ex: example@gmail.com)'
    )
    password = forms.CharField(
        label="Mot de passe d'application",
        widget=forms.PasswordInput(render_value=True),
        help_text=mark_safe(
            '<strong style="color: #113329; display: block; margin-top: 10px; margin-bottom: 10px;"'
            ' style="font-size: 14px;">Comment générer un mot de passe d\'application Gmail :</strong>'
            '<ol style="background-color: #f8f9fa; padding: 15px 20px; border-radius: 4px; border-left: 4px solid #417690; '
            'font-size: 13px; line-height: 1.8; color: #333;">'
            '<li><strong>Activer la vérification en 2 étapes :</strong>'
            '<ul style="margin-top: 5px;">'
            '<li>Allez sur <a href="https://myaccount.google.com/security" target="_blank" style="color: #0066cc;">'
            'myaccount.google.com/security</a></li>'
            '<li>Sous "Connexion à Google", cliquez sur <strong>Vérification en 2 étapes</strong></li>'
            '<li>Suivez le processus d\'installation (numéro de téléphone requis)</li>'
            '</ul>'
            '</li>'
            '<li><strong>Générer le mot de passe d\'application :</strong>'
            '<ul style="margin-top: 5px;">'
            '<li>Allez sur <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color: #0066cc;">'
            'myaccount.google.com/apppasswords</a></li>'
            '<li>Sélectionnez : <strong>Application: Mail</strong>, <strong>Appareil: Autre (Nom personnalisé)</strong></li>'
            '<li>Entrez un nom (ex: "Django Phishing")</li>'
            '<li>Cliquez sur <strong>Générer</strong></li>'
            '<li>Copiez le mot de passe à 16 caractères (les espaces sont facultatifs)</li>'
            '<li>Collez-le dans ce champ ci-dessous</li>'
            '</ul>'
            '</li>'
            '<li><strong>Exemple de mot de passe :</strong> <code style="background-color: #e8e8e8; padding: 3px 6px; '
            'border-radius: 3px;">qwer tyui asdf ghjk</code></li>'
            '</ol>'
        )
    )
    is_active = forms.BooleanField(
        label='Actif',
        required=False,
        initial=True,
        help_text='Décochez pour désactiver temporairement ce compte sans le supprimer'
    )

    class Meta:
        model = SmtpAccount
        fields = ['email', 'password', 'is_active']



class LandingPageForm(forms.ModelForm):
    class Meta:
        model = LandingPage
        fields = ['title', 'slug', 'content', 'css_content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'code-editor',
                'rows': 20,
                'spellcheck': 'false',
                'style': 'font-family: monospace; white-space: pre;'
            }),
            'css_content': forms.Textarea(attrs={
                'class': 'code-editor',
                'rows': 15,
                'spellcheck': 'false',
                'style': 'font-family: monospace; white-space: pre;'
            }),
        }


class CampaignTargetBulkForm(forms.Form):
    campaign = forms.ModelChoiceField(queryset=Campaign.objects.all(), required=True)
    targets = forms.ModelMultipleChoiceField(
        queryset=Target.objects.all(),
        widget=forms.SelectMultiple(attrs={'size': 15, 'style': 'width:100%'}),
        required=True,
        label="Select targets (Ctrl+click for multiple)"
    )