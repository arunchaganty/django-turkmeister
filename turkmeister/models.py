from django.db import models, transaction
from django.contrib.postgres.fields import JSONField

from . import utils

class Task(models.Model):
    name = models.CharField(help_text="Name of the task (inferred from classname)")
    version = models.IntegerField(help_text="Version of this task (auto-updated)")
    created = models.DateTimeField(auto_now=True, help_text="When the task was added")

    def get(self):
        # TODO: Get the task from the tasks directory.
        raise NotImplementedError()

class Batch(models.Model):
    UPLOADING = 0
    PENDING_ANNOTATION = 1
    PENDING_AGGREGATION = 2
    DONE = 3
    CANCELLED = 4
    STATES = (
        (UPLOADING, "Uploading..."),
        (PENDING_ANNOTATION, "Annotating..."),
        (PENDING_AGGREGATION, "Aggregating..."),
        (DONE, "Done."),
        (CANCELLED, "Cancelled."),
        )

    task = models.ForeignKey(Task, help_text="Task to use for this batch")
    created = models.DateTimeField(auto_now=True, help_text="When the batch was created")
    state = models.IntegerField(default=UPLOADING, help_text="Current state of the batch")

    def sync(self):
        for hit in self.hits:
            hit.sync()

    def cancel(self):
        with transaction.atomic():
            for hit in self.hits:
                hit.cancel()
            self.state = Batch.CANCELLED
            self.save()

class Hit(models.Model):    
    PENDING_ANNOTATION = 0
    PENDING_AGGREGATION = 1
    DONE = 2
    CANCELLED = 3
    STATES = (
        (PENDING_ANNOTATION, "Annotating..."),
        (PENDING_AGGREGATION, "Aggregating..."),
        (DONE, "Done."),
        (CANCELLED, "Cancelled."),
        )

    id = models.CharField(primary_key=True, help_text="HIT id from AMT")
    batch = models.ForeignKey(Batch, related_name="hits", help_text="Which batch this task belongs to")
    created = models.DateTimeField(auto_now=True, help_text="When the batch was created")
    expected_assignments = models.IntegerField(help_text="How many assignments do we expect?")
    input_data = JSONField(help_text="Input data for this HIT")
    output_data = JSONField(null=True, help_text="Output data for this HIT (set post-aggregation)")
    state = models.IntegerField(default=PENDING_ANNOTATION, help_text="Current state of the batch")

    @property
    def task(self):
        return self.batch.task

    @property
    def mturk(self):
        return utils.get_hit(self.id)

    def extend(self, count=1):
        if utils.increment_assignments(self.id, count=count):
            self.expected_assignments +=1
            self.save()

    def cancel(self):
        return utils.revoke_hit(self.id)

    def update_state(self, new_state):
        if self.state != new_state:
            self.state = new_state
            self.save()

    def sync(self):
        # Get any pending assignments.
        assignments = self.assignments
        for assignment in utils.retrieve_assignments_for_hit(self.id):
            if assignments.filter(id=assignment["AssignmentId"]).exists():
                continue
            else:
                assn = Assignment.from_mturk(assignment)
                assn.save()
                self.task.get().on_assignment_received(assn)

        if assignments.count() == self.expected_assignments:
            if self.task.get().on_hit_complete(self):
                self.update_state(Hit.PENDING_AGGREGATION)

        # Make sure you have a congruent state.
        hit = self.mturk
        if hit['HITStatus'] == 'Assignable':
            self.update_state(Hit.PENDING_ANNOTATION)
        elif hit['HITStatus'] == 'Unassignable':
            # Uh, in this case, we don't do anything?
            pass
        elif hit['HITStatus'] == 'Reviewable' or hit['HITStatus'] == 'Reviewing':
            # The task can also be in a done state, so, no further promises.
            if self.state == Hit.PENDING_ANNOTATION:
                self.update_state(Hit.PENDING_AGGREGATION)
        elif hit['HITStatus'] == 'Disposed':
            # So, this means we're either done or cancelled.
            if self.state == Hit.PENDING_ANNOTATION:
                self.update_state(Hit.CANCELLED)
            if self.state == Hit.PENDING_AGGREGATION:
                self.update_state(Hit.DONE)

class Assignment(models.Model):
    PENDING_VERIFICATION = 0
    ACCEPTED = 1
    REJECTED = 2
    STATES = (
        (PENDING_VERIFICATION, "Verifying..."),
        (ACCEPTED, "Accepted."),
        (REJECTED, "Rejected."),
        )

    id = models.CharField(primary_key=True, help_text="HIT id from AMT")
    hit = models.ForeignKey(Hit, related_name="assignments", help_text="Which batch this task belongs to")
    worker_id = models.CharField(help_text="Identifier for worker (useful)")
    created = models.DateTimeField(auto_now=True, help_text="When the batch was created")
    output_data = JSONField(help_text="Output data for this HIT")
    state = models.IntegerField(default=PENDING_VERIFICATION, help_text="Current state of the batch")

    @classmethod
    def from_mturk(cls, assn):
        """
        Create from an mturk object.
        """
        assert "Output" in assn
        ret = cls(
            id=assn["AssignmentId"],
            hit_id=assn["HITId"],
            worker_id=assn["WorkerId"],
            output_data=assn["Output"],
            )
        if assn["AssignmentStatus"] == "Accepted":
            ret.update_state(cls.ACCEPTED)
        elif assn["AssignmentStatus"] == "Rejected":
            ret.update_state(cls.REJECTED)

        return ret

    @property
    def batch(self):
        return self.hit.batch

    @property
    def task(self):
        return self.hit.batch.task

    @property
    def mturk(self):
        return utils.get_assignment(self.id)

    def update_state(self, new_state):
        if self.state != new_state:
            self.state = new_state
            self.save()

    def sync(self):
        assn = self.mturk

        if assn["AssignmentStatus"] == "Submitted":
            self.update_state(Assignment.PENDING_VERIFICATION)
        elif assn["AssignmentStatus"] == "Accepted":
            self.update_state(Assignment.ACCEPTED)
        elif assn["AssignmentStatus"] == "Rejected":
            self.update_state(Assignment.REJECTED)
