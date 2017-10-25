from django.db import models, transaction
from django.contrib.postgres.fields import JSONField

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

    batch = models.ForeignKey(Batch, related_name="hits", help_text="Which batch this task belongs to")
    created = models.DateTimeField(auto_now=True, help_text="When the batch was created")
    input_data = JSONField(help_text="Input data for this HIT")
    output_data = JSONField(null=True, help_text="Output data for this HIT (set post-aggregation)")
    state = models.IntegerField(default=PENDING_ANNOTATION, help_text="Current state of the batch")

    @property
    def task(self):
        return self.batch.task

    @property
    def mturk(self):
        # TODO: get the mturk object from MTurk
        raise NotImplementedError()

    def sync(self):
        # TODO: sync all your children.
        raise NotImplementedError()

    def extend(self, count=1):
        # TODO: sync all your children.
        raise NotImplementedError()

    def cancel(self):
        # TODO: cancel all your children.
        raise NotImplementedError()

class Assignment(models.Model):    
    PENDING_VERIFICATION = 0
    ACCEPTED = 1
    REJECTED = 2
    STATES = (
        (PENDING_VERIFICATION, "Verifying..."),
        (ACCEPTED, "Accepted."),
        (REJECTED, "Rejected."),
        )

    hit = models.ForeignKey(Hit, related_name="assignments", help_text="Which batch this task belongs to")
    created = models.DateTimeField(auto_now=True, help_text="When the batch was created")
    output_data = JSONField(help_text="Output data for this HIT")
    state = models.IntegerField(default=PENDING_VERIFICATION, help_text="Current state of the batch")

    @property
    def batch(self):
        return self.hit.batch

    @property
    def task(self):
        return self.hit.batch.task

    @property
    def mturk(self):
        # TODO: get the mturk object from MTurk
        raise NotImplementedError()
