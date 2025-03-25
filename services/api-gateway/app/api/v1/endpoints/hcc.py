"""
HCC endpoints for the API Gateway.

This module defines endpoints for HCC code operations.
"""

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_user_optional
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.hcc import HCCCodeRead, HCCCodeList, HCCCategory, HCCRelevanceResult, HCCCodeRequest

from app.services.hcc import HCCService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "/codes",
    response_model=HCCCodeList,
    summary="List HCC codes",
    description="List HCC-relevant diagnosis codes with pagination and filtering."
)
async def list_hcc_codes(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        search: Optional[str] = Query(None, min_length=1),
        category: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional),
        hcc_service: HCCService = Depends(),
) -> Any:
    """
    List HCC-relevant diagnosis codes with pagination and filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        search: Search term for code or description
        category: Filter by HCC category
        db: Database session
        current_user: Current user (optional)
        hcc_service: HCC service

    Returns:
        List of HCC codes
    """
    logger.info(
        "HCC codes list requested",
        skip=skip,
        limit=limit,
        search=search,
        category=category,
        user_id=current_user.id if current_user else None,
    )

    items, total = await hcc_service.list_hcc_codes(
        skip=skip,
        limit=limit,
        search=search,
        category=category,
    )

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/codes/{code}",
    response_model=HCCCodeRead,
    summary="Get HCC code details",
    description="Get detailed information about a specific HCC code."
)
async def get_hcc_code(
        code: str = Path(..., description="ICD-10 code"),
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional),
        hcc_service: HCCService = Depends(),
) -> Any:
    """
    Get detailed information about a specific HCC code.

    Args:
        code: ICD-10 code
        db: Database session
        current_user: Current user (optional)
        hcc_service: HCC service

    Returns:
        HCC code details

    Raises:
        HTTPException: If the code is not found
    """
    logger.info(
        "HCC code details requested",
        code=code,
        user_id=current_user.id if current_user else None,
    )

    hcc_code = await hcc_service.get_hcc_code(code)

    if not hcc_code:
        logger.warning(
            "HCC code not found",
            code=code,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HCC code not found",
        )

    return hcc_code


@router.get(
    "/categories",
    response_model=List[HCCCategory],
    summary="List HCC categories",
    description="Get a list of all HCC categories and their descriptions."
)
async def list_hcc_categories(
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional),
        hcc_service: HCCService = Depends(),
) -> Any:
    """
    Get a list of all HCC categories and their descriptions.

    Args:
        db: Database session
        current_user: Current user (optional)
        hcc_service: HCC service

    Returns:
        List of HCC categories
    """
    logger.info(
        "HCC categories list requested",
        user_id=current_user.id if current_user else None,
    )

    categories = await hcc_service.list_hcc_categories()
    return categories


@router.get(
    "/statistics",
    response_model=Dict[str, Any],
    summary="Get HCC statistics",
    description="Get statistics about HCC codes and their usage in the system."
)
async def get_hcc_statistics(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        hcc_service: HCCService = Depends(),
) -> Any:
    """
    Get statistics about HCC codes and their usage in the system.

    Args:
        db: Database session
        current_user: Current authenticated user
        hcc_service: HCC service

    Returns:
        HCC statistics
    """
    logger.info(
        "HCC statistics requested",
        user_id=str(current_user.id),
    )

    statistics = await hcc_service.get_hcc_statistics()
    return statistics


@router.post(
    "/check",
    response_model=HCCRelevanceResult,
    summary="Check HCC relevance",
    description="Check if a diagnosis code or text is HCC-relevant."
)
async def check_hcc_relevance(
        request: HCCCodeRequest,
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional),
        hcc_service: HCCService = Depends(),
) -> Any:
    """
    Check if a diagnosis code or text is HCC-relevant.

    Args:
        request: Diagnosis code or text to check
        db: Database session
        current_user: Current user (optional)
        hcc_service: HCC service

    Returns:
        HCC relevance check result
    """
    logger.info(
        "HCC relevance check requested",
        diagnosis_code=request.diagnosis_code,
        diagnosis_text=request.diagnosis_text,
        user_id=current_user.id if current_user else None,
    )

    # If code is provided, check directly
    if request.diagnosis_code:
        hcc_code = await hcc_service.get_hcc_code(request.diagnosis_code)

        if hcc_code:
            return {
                "is_relevant": True,
                "code": hcc_code["code"],
                "category": hcc_code["category"],
                "confidence": 1.0,
                "alternatives": [],
                "explanation": f"The code {request.diagnosis_code} is directly identified as HCC-relevant."
            }
        else:
            # Code not found in HCC list
            # This would normally integrate with the Vertex AI service to check for relevance
            # For now, we'll provide a simple fallback
            return {
                "is_relevant": False,
                "code": request.diagnosis_code,
                "category": None,
                "confidence": 0.9,
                "alternatives": [],
                "explanation": f"The code {request.diagnosis_code} is not found in the HCC-relevant codes list."
            }

    # If only text is provided
    elif request.diagnosis_text:
        # This would normally use the LLM to get the most likely ICD-10 code
        # For now, we'll implement a simple search in the descriptions
        df = await hcc_service._ensure_hcc_codes_loaded()

        # Try to find matches in description
        search_term = request.diagnosis_text.lower()
        matched_rows = df[df["Description"].str.contains(search_term, case=False, na=False)]

        if len(matched_rows) > 0:
            # Get the first match
            best_match = matched_rows.iloc[0]
            code = best_match["ICD-10-CM Codes"]

            # Get alternatives (up to 3)
            alternatives = []
            if len(matched_rows) > 1:
                for _, row in matched_rows.iloc[1:4].iterrows():
                    alternatives.append(row["ICD-10-CM Codes"])

            return {
                "is_relevant": True,
                "code": code,
                "category": best_match.get("Tags"),
                "confidence": 0.85,  # Lower confidence because we're matching on text
                "alternatives": alternatives,
                "explanation": f"The diagnosis '{request.diagnosis_text}' matches HCC-relevant code {code}."
            }
        else:
            return {
                "is_relevant": False,
                "code": None,
                "category": None,
                "confidence": 0.7,
                "alternatives": [],
                "explanation": f"No matching HCC-relevant codes found for '{request.diagnosis_text}'."
            }

    # If neither code nor text provided
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either diagnosis_code or diagnosis_text must be provided"
        )

@router.get("/verify-file")
async def verify_hcc_file():
    """
    Verify that the HCC codes file exists and is accessible.

    Returns:
        Status message and file information
    """
    from app.core.dependencies import get_hcc_codes_path
    import os

    try:
        # Get HCC codes path
        hcc_codes_path = get_hcc_codes_path()

        # Check if file exists
        file_exists = hcc_codes_path.exists()

        # Get environment variables
        env_path = os.environ.get("HCC_CODES_PATH", "Not set")
        input_dir = os.environ.get("INPUT_DIR", "Not set")

        # List files in data directory
        data_dir = Path(input_dir) if os.path.isabs(input_dir) else Path(".") / input_dir
        files = []
        if data_dir.exists():
            files = [f.name for f in data_dir.iterdir() if f.is_file()]

        # Return status
        return {
            "file_exists": file_exists,
            "file_path": str(hcc_codes_path),
            "environment": {
                "HCC_CODES_PATH": env_path,
                "INPUT_DIR": input_dir
            },
            "data_directory": {
                "path": str(data_dir),
                "exists": data_dir.exists(),
                "files": files
            }
        }

    except Exception as e:
        logger.exception(f"Error verifying HCC file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error verifying HCC file: {str(e)}"
        )