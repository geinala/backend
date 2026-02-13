"""Example simulation job handler - demonstrates patterns and best practices."""

from datetime import datetime
from rq import current_job
from app.schemas import SimulationConfig, JobResult


def process_simulation(config_data: dict) -> dict:
    """
    Example simulation job handler.
    
    This handler demonstrates:
    - Input validation with Pydantic
    - Progress tracking via job metadata
    - Error handling
    - Structured output
    
    Args:
        config_data: Dictionary containing:
            - name: str - Simulation identifier
            - parameters: dict - Simulation parameters
            - timeout: int - Job timeout in seconds
    
    Returns:
        Dictionary with status and results
        
    Raises:
        ValidationError: If config_data is invalid
        Exception: On simulation failure
    """
    
    job = current_job()
    
    # Step 1: Validate input
    try:
        config = SimulationConfig(**config_data)
    except Exception as e:
        job.set_status('failed')
        raise ValueError(f"Invalid simulation config: {str(e)}")
    
    # Step 2: Initialize job metadata
    job.meta['status'] = 'initializing'
    job.meta['progress'] = 0
    job.meta['config_name'] = config.name
    job.save_meta()
    
    try:
        # Step 3: Setup phase
        job.meta['status'] = 'setup'
        job.meta['progress'] = 10
        job.save_meta()
        
        simulate_setup(config)
        
        # Step 4: Execution phase
        job.meta['status'] = 'running'
        results = []
        
        for i in range(100):
            # Simulate iterative processing
            result = simulate_iteration(config, i)
            results.append(result)
            
            # Update progress every 10 iterations
            if i % 10 == 0:
                job.meta['progress'] = 10 + int((i / 100) * 80)
                job.save_meta()
        
        # Step 5: Finalization
        job.meta['status'] = 'finalizing'
        job.meta['progress'] = 95
        job.save_meta()
        
        final_result = finalize_simulation(results)
        
        # Step 6: Success
        job.meta['status'] = 'completed'
        job.meta['progress'] = 100
        job.save_meta()
        
        # Return validated result
        return JobResult(
            status="success",
            result=final_result,
            job_id=job.id,
            timestamp=datetime.now().isoformat()
        ).model_dump()
        
    except Exception as e:
        # Failure handling
        job.meta['status'] = 'failed'
        job.meta['error'] = str(e)
        job.save_meta()
        
        return JobResult(
            status="failed",
            error=str(e),
            job_id=job.id,
            timestamp=datetime.now().isoformat()
        ).model_dump()


def simulate_setup(config: SimulationConfig) -> None:
    """Setup phase of simulation."""
    # Initialize resources, load models, etc.
    pass


def simulate_iteration(config: SimulationConfig, iteration: int) -> dict:
    """Single iteration of simulation."""
    # Perform computation
    return {
        "iteration": iteration,
        "value": iteration * 0.1
    }


def finalize_simulation(results: list) -> dict:
    """Aggregate and finalize results."""
    return {
        "iteration_count": len(results),
        "values": results,
        "summary": {
            "min": min(r["value"] for r in results),
            "max": max(r["value"] for r in results),
            "avg": sum(r["value"] for r in results) / len(results)
        }
    }
