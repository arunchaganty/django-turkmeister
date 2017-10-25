"""
Every task module should expose a TaskView and optionally a InspectView.
"""
import logging
from urllib.parse import urlencode

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect

from turkmeister.models import Hit

logger = logging.getLogger(__name__)

class Task(object):
    """
    A task is responsible for rendering a page to show to turkers
    and handling their response.
    """

    def get_task_params(self, datum):
        """
        Return the task parameters used for the HIT @datum.
        """
        raise NotImplementedError()
        # return {
        #     "Title": "Short title",
        #     "Description": "Longer description,
        #     "FrameHeight": "1200",
        #     "AssignmentDurationInSeconds": "300",
        #     "LifetimeInSeconds": "86400",
        #     "MaxAssignments": "3",
        #     "Reward": "0.10",
        #     }

    def _view_task(self, request):
        if not request.GET or "hitId" not in request.GET:
            hit = Hit.objects.first()
            return HttpResponseRedirect(request.url + '?' + urlencode({
                "assignmentId": "TEST_ASSIGNMENT",
                "hitId": hit.id,
                "workerId": "TEST_WORKER",
                }))
        hit = get_object_or_404(Hit, id=request.GET["hitId"])

        return self.view_task(request, hit)

    def view_task(self, request, hit):
        """
        Code to display HIT.
        """
        # NOTE: You should have your own implementation here.
        return render(request, 'task.html', {'input': hit})

    def inspect_task(self, request, hit):
        raise NotImplementedError()

    def on_hit_complete(self, hit):
        logger.info("HIT complete: %s", hit.id)

    def on_assignment_received(self, assn):
        logger.info("Assignment recieved for HIT: %s", assn.hit_id)

    def on_batch_complete(self, batch):
        logger.info("Batch %s completed!", batch.id)
