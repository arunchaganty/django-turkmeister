# django-turkmeister
A Django App to handle the boilerplate of launching a custom task with Amazon Mechanical Turk

Turkmeister's goal is to help with the iterated refinement of tasks
for AMT, which means the focus is to make it easy to create new
versions of a task and aggregate results.

The contract between you, the user, and Turkmeister is that you provide a single task directory containing:
  + `task.py`: A class-based view (more on this below) that handles:
    - the default title, description for a task.
    - what to show the turker.
    - (optional) how to view the turker's responses.
    - how many assignments to provide by default, as well an expiry time.
    - how to aggregate/verify the responses.
    - hooks for handling when an assignment is completed, a task is completed or a batch is completed.
  + `static/`: a directory that will be served / searched when rendering templates.
  + `data.json`: (optional) the data to be uploaded (more data can be uploaded as well).

There is one assumption, namely that each task instance takes a single
JSON object as input (`$input`) and will send back a single JSON
object as output (`$output`). If the JSON object contains a `price`
field, it will be used when creating HITs.

In return, Turkmeister will handle the following boilerplate:
  + Create tasks on AMT with dynamic pricing.
  + An admin interface to help you manage each batch.
  + Allow you to custom verify the HITs.
  + Handle payments on completion of the task.

# The Task Class.

TBD

# Installation.

TBD

1. Include turkmeister in any django-project you wish.
2. Create a cron job to make sure that we are in sync with mturk (this is important!)

# Internals

Turkmeister seeks to handle the following problems:
- model structure (2hrs)
    - Task
        - name, version, timestamp, classname
    - Batch
        - task, timestamp, state = {uploading, pending-annotation, pending-aggregation, done}
        - sync() -> ensures the HIT states of all children are properly accounted for.
        - .cancel()
    - HIT
        - batch, input_data, HITID, output_data (NULL), state = {pending-annotation, pending-aggregation, done, cancelled}
        - sync() -> ensures the HIT state is accurately reflected, and all assignments are accounted for.
        - extend() -> increases assignment for some reason.
        - cancel() -> cancels the task.
        - .mturk -> gets mturk object
    - Assignment
        - hit, response, state = {pending-aggregation, accepted, rejected}
        - sync() -> ensures the HIT state is accurately reflected.

        - .mturk -> gets mturk object
- views (2hrs)
    - serve/HIT_ID, ASSIGNMENT_ID
        - gets the task view from tasks and responds using it.
        - when getting the data via post, send the data to task (which can do whatever).
    - @login: review/task/batch/hit/
        - upload a new batch
        - download the output of a batch.
- admin (1hr)
    - standard views.
    - actions to sync/cancel/extend a batch, hit, assignment.
