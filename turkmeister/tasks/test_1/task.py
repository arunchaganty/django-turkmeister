"""
Every task module should expose a TaskView and optionally a InspectView.
"""
from urllib.parse import urlencode

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect

from turkmeister.models import Hit
from turkmeister.task import Task

class MyTask(Task):
    """
    A task is responsible for rendering a page to show to turkers
    and handling their response.
    """
    name = "test"

    def get_task_params(self, _):
        """
        Return the task parameters used for the HIT @datum.
        """
        return {
            "Title": "Short title",
            "Description": "Longer description",
            "FrameHeight": "1200",
            "AssignmentDurationInSeconds": "300",
            "LifetimeInSeconds": "86400",
            "MaxAssignments": "3",
            "Reward": "0.10",
            }
