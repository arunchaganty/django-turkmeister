"""
Utilities for mechanical turk.
"""
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import boto3
from boto.mturk.question  import ExternalQuestion

from django.conf import settings
#from .apps import TurkmeisterConfig as Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def connect():
    """
    Connect to mechanical turk to sandbox or actual depending on
    @host_str with prompt for actual unless @forced
    """
    endpoint_url = settings.AMT_ENDPOINT
    logger.debug("Connecting to MTurk (%s)", endpoint_url)

    conn = boto3.client('mturk',
                        endpoint_url=settings.AMT_ENDPOINT,
                        aws_access_key_id=settings.AWS_ACCESS_KEY,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_REGION,
                       )
    logger.debug("Successfully connected.")
    return conn

_CONN = connect()

# HIT functions.
def create_hit(task_settings, conn=None, url=settings.URL):
    """
    Create a hit on mturk with @question in a @batch using @mturk_connection
    """
    assert "Title" in task_settings
    assert "Description" in task_settings
    assert "MaxAssignments" in task_settings
    assert "Reward" in task_settings
    assert "AssignmentDurationInSeconds" in task_settings
    assert "LifetimeInSeconds" in task_settings

    if conn is None:
        conn = _CONN

    logger.debug("Creating HIT")
    question = ExternalQuestion(url, task_settings.get("FrameHeight", 800))
    response = conn.create_hit(Question=question.get_as_xml(),
                               Title=task_settings["Title"],
                               Description=task_settings["Description"],
                               MaxAssignments=task_settings["MaxAssignments"],
                               AssignmentDurationInSeconds=task_settings["AssignmentDurationInSeconds"],
                               LifetimeInSeconds=task_settings["LifetimeInSeconds"],
                               Reward=task_settings["Reward"],
                               QualificationRequirements=task_settings.get("QualificationRequirements"),
                              )
    logger.debug("HIT created (%s, %s).", response['HIT']['HITTypeId'], response['HIT']['HITId'])
    return response['HIT']

def get_hit(hit_id, conn=None):
    if conn is None:
        conn = _CONN

    return conn.get_hit(HITId=hit_id)['HIT']

def get_assignment(assignment_id, conn=None):
    if conn is None:
        conn = _CONN
    ret = conn.get_hit(AssignmentId=assignment_id)['Assignment']
    if "Answer" in ret:
        ret["Output"] = parse_assignment_response(ret["Answer"])

    return ret

class HitMustBeReviewed(Exception):
    pass

def revoke_hit(hit_id, conn=None):
    """
    Revokes a HIT by first expiring it and then trying to delete it.
    This method will raise an RequestException if the HIT needs to be reviewed.
    """
    if conn is None:
        conn = _CONN

    hit = get_hit(conn, hit_id)

    # Check if already disposed of.
    if hit["HITStatus"] == "Disposed":
        return False

    conn.update_expiration_for_hit(HITId=hit_id, ExpireAt=datetime.now())
    hit = get_hit(conn, hit_id)

    # Verify that the statis is Reviewable
    assert hit["HITStatus"] == "Reviewable" or hit["HITStatus"] == "Unassignable"
    assignments_inflight = hit['MaxAssignments'] - (hit['NumberOfAssignmentsAvailable'] + hit['NumberOfAssignmentsCompleted'] + hit['NumberOfAssignmentsPending'])
    if assignments_inflight > 0:
        logger.error("HIT must be reviewed")
        raise HitMustBeReviewed(hit_id)

    conn.delete_hit(HITId=hit_id)
    logger.info("Finished revoking mturk_hit %s", hit_id)
    return True

def test_create_revoke_hit():
    """Test hit creation on the sandbox"""

    params = {
        "Title": "Find relations between people, companies and places",
        "Description": "You'll need to pick which relationship is described between a single pair of people, places or organisations in a sentece.",
        "AssignmentDurationInSeconds": "300",
        "FrameHeight": "1200",
        "MaxAssignments": "3",
        "LifetimeInSeconds": "86400",
        "Reward": "0.10",
        }

    conn = connect()
    _, hit_id = create_hit(conn, params)
    assert hit_id is not None

    # Get this HIT and ensure it has the desired properties.
    r = get_hit(conn, hit_id)
    assert r is not None
    assert r['Title'] == params['Title']
    assert r['Description'] == params['Description']
    assert r['Reward'] == params['Reward']
    assert r['HITStatus'] == 'Assignable'

    assert revoke_hit(conn, hit_id)
    r = get_hit(conn, hit_id)
    assert r is not None
    assert r['HITStatus'] == 'Disposed'

def renew_hit(hit_id, time=None, conn=None):
    if conn is None:
        conn = _CONN

    if time is None:
        time = datetime.now() + timedelta(days=1)
    logger.info("Updating expiry for HIT %s to %s", hit_id, time)

    conn.update_expiration_for_hit(
        HITId=hit_id,
        ExpireAt=time
        )
    return True

def increment_assignments(hit_id, count=1, conn=None):
    if conn is None:
        conn = _CONN

    logger.info("Incrementing %s assignments for HIT %s", count, hit_id)
    conn.create_additional_assignments_for_hit(
        HITId=hit_id,
        NumberOfAdditionalAssignments=count,
        ) # TODO: maybe use UniqueRequestToken

    return renew_hit(conn, hit_id, datetime.now() + timedelta(days=1))

class MTurkInvalidStatus(Exception):
    pass

def retrieve_assignments_for_hit(hit_id, conn=None):
    """Get all the completed assignments for the given @hit_id and insert into the database"""
    if conn is None:
        conn = _CONN

    hit_response = conn.list_assignments_for_hit(HITId = hit_id)
    assignments = hit_response['Assignments']

    ret = []
    for assignment_response in assignments:
        assignment_response["Output"] = parse_assignment_response(assignment_response["Answer"])
        ret.append(assignment_response)
    return ret

def reject_assignment(assignment_id, message=None, conn=None):
    if conn is None:
        conn = _CONN

    assn = conn.get_assignment(AssignmentId = assignment_id)
    status = assn["Assignment"]["AssignmentStatus"]
    if status == "Approved":
        raise MTurkInvalidStatus("Assignment {} has already been approved!".format(assignment_id))
    elif status == "Rejected":
        return False
    elif status != "Submitted":
        raise MTurkInvalidStatus("Assignment should have status {}, but has status {}".format("Submitted", status))

    conn.reject_assignment(AssignmentId = assignment_id, message = message)
    return True

def approve_assignment(assignment_id, conn=None):
    if conn is None:
        conn = _CONN

    assn = conn.get_assignment(AssignmentId = assignment_id)
    status = assn["Assignment"]["AssignmentStatus"]
    if status == "Approved":
        return False
    elif status == "Rejected":
        raise MTurkInvalidStatus("Assignment {} has already been rejected!".format(assignment_id))
    elif status != "Submitted":
        raise MTurkInvalidStatus("Assignment {} should have status {}, but has status {}".format(assignment_id, "Submitted", status))

    conn.approve_assignment(AssignmentId = assignment_id)
    return True

def _parse_assignment_response(response):
    """Insert an assignment based on mturk_response"""
    answers = ET.fromstring(response)
    xml_fields = {}
    for answer in answers.findall('./'):
        if 'Answer' in answer.tag:
            field = None
            for child in answer.findall('./'):
                if 'QuestionIdentifier' in child.tag:
                    field = child.text
                if 'FreeText' in child.tag:
                    xml_fields[field] = child.text
    return xml_fields

def parse_assignment_response(response):
    """Insert an assignment based on mturk_response"""
    xml_fields = _parse_assignment_response(response)
    return json.loads(xml_fields["output"])

def test_insert_assignment_from_response():
    sample_response = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<QuestionFormAnswers xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2005-10-01/QuestionFormAnswers.xsd">\n<Answer>\n<QuestionIdentifier>csrfmiddlewaretoken</QuestionIdentifier>\n<FreeText>BdcX1JGw8D7v25lyqSe7EQV7JXeJEVULNhshEoaSR8zN1Q95sZkAI9UF8vFwt7mm</FreeText>\n</Answer>\n<Answer>\n<QuestionIdentifier>mentionPair</QuestionIdentifier>\n<FreeText>span-gloss:span-gloss</FreeText>\n</Answer>\n<Answer>\n<QuestionIdentifier>workerId</QuestionIdentifier>\n<FreeText>A17AH7B74XRKX1</FreeText>\n</Answer>\n<Answer>\n<QuestionIdentifier>workerTime</QuestionIdentifier>\n<FreeText>90.555</FreeText>\n</Answer>\n<Answer>\n<QuestionIdentifier>submit</QuestionIdentifier>\n<FreeText/>\n</Answer>\n<Answer>\n<QuestionIdentifier>response</QuestionIdentifier>\n<FreeText>[{"apples":0.3,"bananas":["1",2]}]</FreeText>\n</Answer>\n<Answer>\n<QuestionIdentifier>comment</QuestionIdentifier>\n<FreeText/>\n</Answer>\n</QuestionFormAnswers>\n'
    response = parse_assignment_response(sample_response)
    assert response == [{"apples":0.3,"bananas":["1",2]}]
