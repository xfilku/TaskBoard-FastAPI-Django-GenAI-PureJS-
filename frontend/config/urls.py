"""Route Django admin and the server-rendered TaskBoard account and board pages."""

from django.contrib import admin
from django.urls import path
from pages.views import (
    board_detail_page,
    create_board_page,
    delete_board_page,
    delete_task_page,
    edit_task_page,
    home,
    login_page,
    logout_user,
    plan_preview_page,
    register_page,
    save_plan_page,
    update_task,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("login/", login_page, name="login"),
    path("register/", register_page, name="register"),
    path("logout/", logout_user, name="logout"),
    path("boards/new/", create_board_page, name="board_create"),
    path("boards/<int:board_id>/", board_detail_page, name="board_detail"),
    path("boards/<int:board_id>/plan/", plan_preview_page, name="plan_preview"),
    path("boards/<int:board_id>/delete", delete_board_page, name="delete_board"),
    path("boards/<int:board_id>/plan/save/", save_plan_page, name="save_plan"),
    path("boards/<int:board_id>/task/<int:task_id>/", update_task, name="update_task"),
    path("boards/<int:board_id>/task/<int:task_id>/delete/", delete_task_page, name="delete_task"),
    path("boards/<int:board_id>/task/<int:task_id>/edit/", edit_task_page, name="edit_task"),
]
