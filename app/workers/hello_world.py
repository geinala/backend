"""Simple hello world worker - just prints a message."""


def hello_world() -> dict[str, str]:
    from rq.job import get_current_job
    
    job = get_current_job()
    
    assert job is not None, "Function must be run within an RQ worker context"
    
    print("\n" + "="*60)
    print("👋 HELLO WORLD FROM WORKER!")
    print("="*60 + "\n")
    
    job.meta['status'] = 'completed' 
    job.save_meta()
    
    return {
        "status": "success",
        "message": "Hello world from RQ worker!",
        "job_id": job.id
    }
