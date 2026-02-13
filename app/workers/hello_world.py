def hello_world() -> dict[str, str]:
    from rq.job import get_current_job
    
    job = get_current_job()
    
    assert job is not None, "Function must be run within an RQ worker context"
    
    job.meta['status'] = 'completed' 
    job.save_meta()
    
    return {
        "status": "success",
        "message": "Hello world from RQ worker!",
        "job_id": job.id
    }
