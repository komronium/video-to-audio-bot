import io
from datetime import date, timedelta
from typing import List, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User


async def joins_per_days(db: AsyncSession, days: int) -> Tuple[List[date], List[int]]:
    """Return lists of dates and counts of users joined for the last `days` days (inclusive).

    Dates are returned as `datetime.date` objects in chronological order.
    """
    today = date.today()
    start = today - timedelta(days=days - 1)

    stmt = (
        select(User.joined_at, func.count(User.user_id))
        .where(User.joined_at >= start)
        .group_by(User.joined_at)
        .order_by(User.joined_at)
    )
    rows = (await db.execute(stmt)).all()
    counts = {row[0]: row[1] for row in rows}

    dates = [start + timedelta(days=i) for i in range(days)]
    values = [int(counts.get(d, 0)) for d in dates]
    return dates, values


def create_join_chart_image(dates: List[date], values: List[int], title: str = "New users") -> io.BytesIO:
    """Create a PNG chart (bar) for given dates and values and return a BytesIO buffer.

    Uses matplotlib (must be installed). The returned buffer is seeked to 0.
    """
    try:
        import matplotlib

        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except Exception as e:
        raise RuntimeError("matplotlib is required to generate charts") from e

    fig, ax = plt.subplots(figsize=(8, 3))
    ax.bar(dates, values, color="#4c72b0")
    ax.set_title(title)
    ax.set_ylabel("New users")
    ax.set_xlabel("")

    # Format x-axis as dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf
