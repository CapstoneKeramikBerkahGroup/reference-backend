"""
Progress tracking untuk background processing NLP
"""

from typing import Dict, Any
import time
import logging

logger = logging.getLogger(__name__)

# Global dictionary untuk track progress
processing_status: Dict[int, Dict[str, Any]] = {}


def init_progress(dokumen_id: int):
    """Initialize progress tracking"""
    processing_status[dokumen_id] = {
        "status": "queued",
        "progress": 0,
        "current_step": "Queued for processing...",
        "started_at": time.time(),
        "message": None,
        "error": None
    }
    logger.info(f"📊 Progress initialized for document {dokumen_id}")


def update_progress(dokumen_id: int, progress: int, step: str):
    """Update progress"""
    if dokumen_id in processing_status:
        processing_status[dokumen_id].update({
            "status": "processing",
            "progress": progress,
            "current_step": step
        })
        logger.info(f"📊 Document {dokumen_id}: {progress}% - {step}")
    else:
        logger.warning(f"⚠️ Tried to update progress for unknown document {dokumen_id}")


def complete_progress(dokumen_id: int, message: str = "Processing completed"):
    """Mark as completed"""
    if dokumen_id in processing_status:
        processing_status[dokumen_id].update({
            "status": "completed",
            "progress": 100,
            "current_step": "Done",
            "message": message,
            "completed_at": time.time()
        })
        logger.info(f"✅ Document {dokumen_id} processing completed")


def fail_progress(dokumen_id: int, error: str):
    """Mark as failed"""
    if dokumen_id in processing_status:
        processing_status[dokumen_id].update({
            "status": "failed",
            "progress": 0,
            "current_step": "Failed",
            "error": error,
            "failed_at": time.time()
        })
        logger.error(f"❌ Document {dokumen_id} processing failed: {error}")
    else:
        logger.warning(f"⚠️ Tried to mark unknown document {dokumen_id} as failed")


def get_progress(dokumen_id: int) -> Dict[str, Any]:
    """Get current progress"""
    return processing_status.get(dokumen_id, {
        "status": "unknown",
        "progress": 0,
        "message": "No processing found for this document"
    })


def clear_progress(dokumen_id: int):
    """Clear progress tracking"""
    if dokumen_id in processing_status:
        del processing_status[dokumen_id]
