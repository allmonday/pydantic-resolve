from django.db import models


class SchoolOrm(models.Model):
    name = models.CharField(max_length=100)
    deleted = models.BooleanField(default=False)

    class Meta:
        app_label = "tests_contrib_django"
        db_table = "school"


class StudentOrm(models.Model):
    name = models.CharField(max_length=100)
    deleted = models.BooleanField(default=False)
    school = models.ForeignKey(
        SchoolOrm,
        on_delete=models.CASCADE,
        related_name="students",
    )

    class Meta:
        app_label = "tests_contrib_django"
        db_table = "student"


class CourseOrm(models.Model):
    title = models.CharField(max_length=100)
    deleted = models.BooleanField(default=False)
    students = models.ManyToManyField(
        StudentOrm,
        related_name="courses",
    )

    class Meta:
        app_label = "tests_contrib_django"
        db_table = "course"
