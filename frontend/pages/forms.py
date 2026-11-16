"""Validate browser form input before sending it to the TaskBoard API."""

from django import forms
from django.forms import BaseFormSet, formset_factory


class LoginForm(forms.Form):
    """Collect account credentials without trimming the password."""

    email = forms.EmailField(label="E-mail")
    password = forms.CharField(label="Hasło", widget=forms.PasswordInput, strip=False)


class RegisterForm(LoginForm):
    """Enforce the API's existing minimum password length at registration."""

    password = forms.CharField(label="Hasło", min_length=5, widget=forms.PasswordInput, strip=False)


class BoardCreateForm(forms.Form):
    """Validate a board name and an optional deadline."""

    name = forms.CharField(label="Nazwa tablicy", min_length=3, max_length=100)
    deadline = forms.DateField(required=False, label="Termin")


class CreateTaskForm(forms.Form):
    """Validate a task title and an optional deadline for creation and editing."""

    title = forms.CharField(label="Tytuł zadania", min_length=5, max_length=300)
    deadline = forms.DateField(
        required=False,
        label="Termin",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )


class PlanPreviewForm(forms.Form):
    """Collect a goal and validate the proposal count before contacting the model."""

    goal = forms.CharField(
        label="Co chcesz osiągnąć?",
        min_length=5,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "class": "ai-goal-input",
                "aria-describedby": "goal-help",
                "placeholder": "Chcę przygotować stronę portfolio, która pokaże moje projekty i umiejętności…",
            }
        ),
    )
    min_elements = forms.IntegerField(label="Minimum zadań", min_value=1, max_value=50, initial=1)
    max_elements = forms.IntegerField(label="Maksimum zadań", min_value=1, max_value=50, initial=10)

    def clean(self) -> dict:
        """Reject an inverted range while retaining the user's submitted goal."""
        data = super().clean()
        min_elements = data.get("min_elements")
        max_elements = data.get("max_elements")

        if min_elements is not None and max_elements is not None and min_elements > max_elements:
            self.add_error(
                "max_elements",
                "Maksymalna liczba wygenerowanych zadań musi być większa lub równa minimalnej.",
            )

        return data


class TaskSuggestionForm(CreateTaskForm):
    """Keep generated titles editable before the user explicitly saves them."""

    title = forms.CharField(
        label="Treść zadania",
        min_length=5,
        max_length=300,
        widget=forms.Textarea(attrs={"rows": 2, "class": "ai-suggestion-input"}),
    )


class BaseTaskSuggestionsFormSet(BaseFormSet):
    """Validate selected suggestions with the same fifty-task limit as the API."""

    def clean(self) -> None:
        """Require at least one selected task and reject duplicate edited titles."""
        super().clean()
        if not self.management_form.is_valid() or any(self.errors):
            return
        rows = [form.cleaned_data for form in self.forms]
        selected = [row["title"] for row in rows if row and not row.get("DELETE")]
        if not selected:
            raise forms.ValidationError("Pozostaw co najmniej jedno zadanie do dodania.")
        normalized = [" ".join(title.casefold().split()) for title in selected]
        if len(set(normalized)) != len(normalized):
            raise forms.ValidationError("Każde wybrane zadanie powinno mieć inny tytuł.")


TaskSuggestionsFormSet = formset_factory(
    TaskSuggestionForm,
    formset=BaseTaskSuggestionsFormSet,
    extra=0,
    can_delete=True,
    max_num=50,
    validate_max=True,
    absolute_max=50,
)
