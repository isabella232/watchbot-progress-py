from __future__ import division

from mock import patch

from mockredis import mock_strict_redis_client
import pytest

from watchbot_progress.backends.redis import RedisProgress
from watchbot_progress.errors import JobDoesNotExist


@pytest.fixture()
def parts():
    return [
        {'source': 'a.tif'},
        {'source': 'b.tif'},
        {'source': 'c.tif'}]


def test_status_no_total(monkeypatch):
    """ Have not created a job with .set_total() yet
    """
    monkeypatch.setenv('WorkTopic', 'abc123')
    with patch('redis.StrictRedis', mock_strict_redis_client):
        with pytest.raises(JobDoesNotExist):
            RedisProgress().status('123')


def test_status(parts, monkeypatch):
    """New job shows all parts remaining
    """
    monkeypatch.setenv('WorkTopic', 'abc123')
    with patch('redis.StrictRedis', mock_strict_redis_client):
        p = RedisProgress()
        p.set_total('123', parts)
        status = p.status('123')
        assert status['total'] == 3
        assert status['remaining'] == 3
        assert status['progress'] == 0


def test_status_part(parts, monkeypatch):
    """Check if part is complete
    """
    monkeypatch.setenv('WorkTopic', 'abc123')
    with patch('redis.StrictRedis', mock_strict_redis_client):
        p = RedisProgress()
        p.set_total('123', parts)
        p.complete_part('123', 0)

        assert p.status('123', part=0)['complete'] is True
        assert p.status('123', part=1)['complete'] is False


def test_status_complete_some(parts, monkeypatch):
    """job shows partial progress
    """
    monkeypatch.setenv('WorkTopic', 'abc123')
    with patch('redis.StrictRedis', mock_strict_redis_client):
        p = RedisProgress()
        p.set_total('123', parts)
        done_yet = p.complete_part('123', 0)
        assert not done_yet

        status = p.status('123')
        assert status['total'] == 3
        assert status['remaining'] == 2
        assert status['progress'] == 1 / 3


def test_status_complete_all(parts, monkeypatch):
    """job shows complete progress
    """
    monkeypatch.setenv('WorkTopic', 'abc123')
    with patch('redis.StrictRedis', mock_strict_redis_client):
        p = RedisProgress()
        p.set_total('123', parts)
        for i, _ in enumerate(parts):
            done_yet = p.complete_part('123', i)
        assert done_yet

        status = p.status('123')
        assert status['total'] == 3
        assert status['remaining'] == 0
        assert status['progress'] == 1.0


def test_failjob(parts, monkeypatch):
    """Mark job as failed works
    """
    monkeypatch.setenv('WorkTopic', 'abc123')
    with patch('redis.StrictRedis', mock_strict_redis_client):
        p = RedisProgress()
        p.set_total('123', parts)
        p.fail_job('123', 'epic fail')
        assert p.status('123')['failed'] is True


def test_metadata(parts, monkeypatch):
    """Setting and getting job metadata works
    """
    monkeypatch.setenv('WorkTopic', 'abc123')
    with patch('redis.StrictRedis', mock_strict_redis_client):
        p = RedisProgress()
        p.set_total('123', parts)
        p.set_metadata('123', {'test': 'foo'})
        assert p.status('123')['metadata']['test'] == 'foo'


@patch('redis.StrictRedis', mock_strict_redis_client)
def test_list_jobids(parts, monkeypatch):
    p = RedisProgress(host='localhost', port=6379, db=0, topic_arn='nope')
    p.set_total('job1', parts)
    p.set_total('job2', parts)
    assert list(p.list_jobs(status=False)) == ['job1', 'job2']


@patch('redis.StrictRedis', mock_strict_redis_client)
def test_list_jobs(parts, monkeypatch):
    p = RedisProgress(host='localhost', port=6379, db=0, topic_arn='nope')
    p.set_total('job1', parts)
    p.set_total('job2', parts)
    assert len(list(p.list_jobs())) == 2


@patch('redis.StrictRedis', mock_strict_redis_client)
def test_list_jobs_meta(parts, monkeypatch):
    p = RedisProgress(host='localhost', port=6379, db=0, topic_arn='nope')
    p.set_total('job1', parts)
    p.set_total('job2', parts)
    p.redis.delete('job1-parts')  # job1-metdata should remain thus still be in list
    assert len(list(p.list_jobs())) == 2


@patch('redis.StrictRedis', mock_strict_redis_client)
def test_list_pending(parts, monkeypatch):
    p = RedisProgress(host='localhost', port=6379, db=0, topic_arn='nope')
    jobid = '123'
    p.set_total(jobid, parts)
    assert len(list(p.list_pending_parts(jobid))) == 3
    p.complete_part(jobid, 0)
    assert len(list(p.list_pending_parts(jobid))) == 2


@patch('redis.StrictRedis', mock_strict_redis_client)
def test_list_pending_nojobs(parts, monkeypatch):
    p = RedisProgress(host='localhost', port=6379, db=0, topic_arn='nope')
    jobid = '123'
    p.set_total(jobid, parts)
    assert len(list(p.list_pending_parts(jobid))) == 3
    p.delete(jobid)
    with pytest.raises(JobDoesNotExist):
        p.list_pending_parts(jobid)


@patch('redis.StrictRedis', mock_strict_redis_client)
def test_delete(parts, monkeypatch):
    p = RedisProgress(host='localhost', port=6379, db=0, topic_arn='nope')
    jobid = '123'
    p.set_total(jobid, parts)
    assert 'total' in p.status(jobid)
    p.delete(jobid)
    with pytest.raises(JobDoesNotExist):
        p.status(jobid)


@patch('redis.StrictRedis', mock_strict_redis_client)
def test_delete_when_done(parts, monkeypatch):
    p = RedisProgress(host='localhost', port=6379, db=0, topic_arn='nope', delete_when_done=True)
    jobid = '123'
    p.set_total(jobid, [parts[0]])
    assert len(list(p.list_pending_parts(jobid))) == 1
    p.complete_part(jobid, 0)
    assert not p.redis.hgetall('123-metadata')
    with pytest.raises(JobDoesNotExist):
        p.status(jobid)


@patch('redis.StrictRedis', mock_strict_redis_client)
def test_no_delete_when_done(parts, monkeypatch):
    p = RedisProgress(host='localhost', port=6379, db=0, topic_arn='nope', delete_when_done=False)
    jobid = '123'
    p.set_total(jobid, [parts[0]])
    assert len(list(p.list_pending_parts(jobid))) == 1
    p.complete_part(jobid, 0)
    assert 'total' in p._decode_dict(p.redis.hgetall('123-metadata'))
    assert p.status(jobid)['remaining'] == 0  # status still works
