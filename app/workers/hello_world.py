"""Hello world worker demonstrating structured logging with wide events.

This worker shows best practices:
- One wide event per job with all context
- Includes timing, status, outcome, and business data
- Uses structured JSON logging for analytics
"""

import time
from rq.job import get_current_job

from app.lib import get_logger

logger = get_logger(__name__)


def hello_world() -> dict[str, str]:
    """Execute hello world job with structured logging.
    
    Demonstrates "wide events" - emitting one context-rich event
    at job completion with all relevant information.
    
    Returns:
        Result dict with status and message
    """
    job = get_current_job()
    assert job is not None, "Function must be run within an RQ worker context"
    
    # Track start time for duration calculation
    start_time = time.time()
    
    # Initialize wide event with job context
    wide_event = {
        "job_id": job.id,
        "event_type": "hello_world_job",
        "status": "running",
    }
    
    try:
        # Simulate job execution
        wide_event["message"] = "Hello world from RQ worker!"
        
        # Update job metadata
        job.meta["status"] = "processing"
        job.save_meta()
        
        # Execute business logic (simulated here)
        result = {
            "status": "success",
            "message": wide_event["message"],
            "job_id": job.id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        
        # Mark success in wide event
        wide_event["outcome"] = "success"
        wide_event["result"] = result
        
        # Update job completed state
        job.meta["status"] = "completed"
        job.save_meta()
        
        return result
        
    except Exception as e:
        # Track failure in wide event
        wide_event["outcome"] = "error"
        wide_event["error"] = {
            "type": type(e).__name__,
            "message": str(e),
        }
        
        job.meta["status"] = "failed"
        job.meta["error"] = str(e)
        job.save_meta()
        
        raise
        
    finally:
        # Calculate total duration
        duration_ms = (time.time() - start_time) * 1000
        wide_event["duration_ms"] = round(duration_ms, 2)
        
        # Emit the wide event with all context
        logger.info(wide_event)
