"""
HCC service for the API Gateway.

This module provides business logic for HCC code operations,
including listing, filtering, and retrieving HCC codes.
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import structlog
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.utils.logging import configure_logging
from app.utils.metrics import HCC_OPERATIONS, HCC_OPERATION_TIME

configure_logging(log_level=settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


class HCCService:
    """Service for HCC code operations."""

    def __init__(self, db: AsyncSession = Depends(get_db)):
        """
        Initialize the HCC service.

        Args:
            db: Database session
        """
        self.db = db
        self._hcc_codes_df = None
        self._categories = None
        self._load_timestamp = None
        self._refresh_interval = 3600  # Refresh cache every hour

    async def _ensure_hcc_codes_loaded(self) -> pd.DataFrame:
        """
        Ensure HCC codes are loaded and up-to-date.

        This method loads HCC codes from the CSV file if they haven't been
        loaded yet, or if the cache is stale.

        Returns:
            DataFrame containing HCC codes
        """
        current_time = time.time()
        if (
                self._hcc_codes_df is None
                or self._load_timestamp is None
                or current_time - self._load_timestamp > self._refresh_interval
        ):
            start_time = time.time()

            # Load HCC codes from CSV
            try:
                from app.core.dependencies import get_hcc_codes_path
                hcc_codes_path = get_hcc_codes_path()

                # Read CSV with pandas
                self._hcc_codes_df = pd.read_csv(hcc_codes_path)

                # Clean up column names (strip whitespace)
                self._hcc_codes_df.columns = self._hcc_codes_df.columns.str.strip()

                # Set load timestamp
                self._load_timestamp = current_time

                # Extract categories
                self._extract_categories()

                duration = time.time() - start_time
                HCC_OPERATIONS.labels(operation="load_codes").inc()
                HCC_OPERATION_TIME.labels(operation="load_codes").observe(duration)

                logger.info(
                    "HCC codes loaded",
                    count=len(self._hcc_codes_df),
                    duration=f"{duration:.4f}s",
                )
            except Exception as e:
                logger.error(
                    "Error loading HCC codes",
                    error=str(e),
                )
                # Return empty DataFrame in case of error
                return pd.DataFrame(columns=["ICD-10-CM Codes", "Description", "Tags"])

        return self._hcc_codes_df

    def _extract_categories(self) -> None:
        """
        Extract unique HCC categories from the loaded HCC codes.

        This method extracts categories and their statistics from the
        loaded HCC codes DataFrame.
        """
        if self._hcc_codes_df is None:
            return

        # Extract tags/categories
        tags_series = self._hcc_codes_df.get("Tags", pd.Series([]))

        # Split multi-category entries and flatten
        all_tags = []
        for tags_str in tags_series.dropna():
            tags = [tag.strip() for tag in str(tags_str).split(',')]
            all_tags.extend(tags)

        # Count occurrences of each category
        tag_counts = pd.Series(all_tags).value_counts()

        # Create categories list
        self._categories = []
        for idx, (tag, count) in enumerate(tag_counts.items()):
            if not tag or tag == "nan":
                continue

            # Get codes in this category
            category_mask = self._hcc_codes_df["Tags"].str.contains(tag, na=False)
            category_codes = self._hcc_codes_df[category_mask]

            # Calculate risk score (placeholder - in a real system this would be calculated)
            avg_risk_score = 0.1 + (idx % 10) / 20

            self._categories.append({
                "id": f"HCC{10 + idx}",
                "name": tag,
                "description": f"{tag} related conditions",
                "avg_risk_score": avg_risk_score,
                "code_count": count,
            })

    async def list_hcc_codes(
            self,
            skip: int = 0,
            limit: int = 100,
            search: Optional[str] = None,
            category: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List HCC codes with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search term for code or description
            category: Filter by HCC category

        Returns:
            Tuple of (list of HCC codes, total count)
        """
        start_time = time.time()

        # Ensure HCC codes are loaded
        df = await self._ensure_hcc_codes_loaded()

        # Apply filters
        filtered_df = df.copy()

        if search:
            # Case-insensitive search in code or description
            search_pattern = re.compile(search, re.IGNORECASE)
            code_mask = filtered_df["ICD-10-CM Codes"].str.contains(search_pattern, na=False)
            desc_mask = filtered_df["Description"].str.contains(search_pattern, na=False)
            filtered_df = filtered_df[code_mask | desc_mask]

        if category:
            # Filter by category
            filtered_df = filtered_df[filtered_df["Tags"].str.contains(category, na=False)]

        # Get total count
        total = len(filtered_df)

        # Apply pagination
        paginated_df = filtered_df.iloc[skip:skip + limit]

        # Before converting to list of dictionaries, replace NaN values with None
        paginated_df = paginated_df.replace({pd.NA: None, pd.NaT: None})

        # Convert to list of dictionaries
        result = []
        for _, row in paginated_df.iterrows():
            # Default risk score based on code position (placeholder)
            risk_score = 0.1 + len(result) / 100

            hcc_code = {
                "code": row["ICD-10-CM Codes"],
                "description": row["Description"],
                "category": row.get("Tags", "Unknown"),
                "risk_score": risk_score,
            }
            result.append(hcc_code)

        # Record metrics
        duration = time.time() - start_time
        HCC_OPERATIONS.labels(operation="list_codes").inc()
        HCC_OPERATION_TIME.labels(operation="list_codes").observe(duration)

        return result, total

    async def get_hcc_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific HCC code.

        Args:
            code: ICD-10 code

        Returns:
            HCC code details or None if not found
        """
        start_time = time.time()

        # Ensure HCC codes are loaded
        df = await self._ensure_hcc_codes_loaded()

        # Find the code
        try:
            code_row = df[df["ICD-10-CM Codes"] == code]
            if len(code_row) == 0:
                return None

            row = code_row.iloc[0]

            # Get related codes (similar codes based on prefix)
            code_prefix = code.split('.')[0]
            related_mask = df["ICD-10-CM Codes"].str.startswith(code_prefix)
            related_codes = df[related_mask & (df["ICD-10-CM Codes"] != code)]["ICD-10-CM Codes"].tolist()[:5]

            # Limit to first 5 related codes
            if len(related_codes) > 5:
                related_codes = related_codes[:5]

            # Create HCC code detail
            result = {
                "code": code,
                "description": row["Description"],
                "category": row.get("Tags", "Unknown"),
                # Placeholder risk score (would be calculated in real system)
                "risk_score": 0.1 + hash(code) % 10 / 20,
                "related_codes": related_codes,
                "documentation_requirements": (
                    f"Document specificity of {row['Description'].lower()}, "
                    f"any complications, and current treatment plan."
                ),
                "common_errors": (
                    "Lack of specificity, missing documentation of severity, "
                    "not documenting treatment or management plan."
                ),
            }

            # Record metrics
            duration = time.time() - start_time
            HCC_OPERATIONS.labels(operation="get_code").inc()
            HCC_OPERATION_TIME.labels(operation="get_code").observe(duration)

            return result

        except Exception as e:
            logger.error(
                "Error retrieving HCC code",
                code=code,
                error=str(e),
            )

            # Record metrics
            duration = time.time() - start_time
            HCC_OPERATIONS.labels(operation="get_code_error").inc()
            HCC_OPERATION_TIME.labels(operation="get_code_error").observe(duration)

            return None

    async def list_hcc_categories(self) -> List[Dict[str, Any]]:
        """
        Get a list of all HCC categories and their descriptions.

        Returns:
            List of HCC categories
        """
        start_time = time.time()

        # Ensure HCC codes are loaded
        await self._ensure_hcc_codes_loaded()

        if self._categories is None:
            self._extract_categories()

        # Record metrics
        duration = time.time() - start_time
        HCC_OPERATIONS.labels(operation="list_categories").inc()
        HCC_OPERATION_TIME.labels(operation="list_categories").observe(duration)

        return self._categories

    async def get_hcc_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about HCC codes and their usage in the system.

        Returns:
            HCC statistics
        """
        start_time = time.time()

        # Ensure HCC codes are loaded
        df = await self._ensure_hcc_codes_loaded()

        # Get total number of HCC codes
        total_codes = len(df)

        # Get top categories
        if self._categories is None:
            self._extract_categories()

        top_categories = []
        for i, category in enumerate(self._categories[:3]):
            # Placeholder percentages - in a real system these would be calculated
            percentage = 25.0 - (i * 3.5)
            top_categories.append({
                "category": category["name"],
                "count": category["code_count"],
                "percentage": percentage,
            })

        # Generate placeholder monthly trend
        import datetime
        current_month = datetime.datetime.now()
        monthly_trend = []
        for i in range(3):
            month = current_month - datetime.timedelta(days=30 * i)
            monthly_trend.append({
                "month": month.strftime("%Y-%m"),
                "count": 250 + (i * 30),
            })
        monthly_trend.reverse()

        # Compile statistics
        stats = {
            "total_hcc_codes": total_codes,
            "top_categories": top_categories,
            "monthly_trend": monthly_trend,
            "avg_hcc_codes_per_document": 3.2,  # Placeholder
            "compliance_rate": 0.87,  # Placeholder
        }

        # Record metrics
        duration = time.time() - start_time
        HCC_OPERATIONS.labels(operation="get_statistics").inc()
        HCC_OPERATION_TIME.labels(operation="get_statistics").observe(duration)

        return stats