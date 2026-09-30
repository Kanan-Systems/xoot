"""The size cap every move, push and drop plan passes before it is shown or written."""

from xoot.exceptions.plan_size_error import PlanSizeError
from xoot.models.item.bulk_create import MAX_PLAN_ITEMS
from xoot.models.item.item import Item
from xoot.models.item.subtree_plan import SubtreePlan


def check_plan_size(root: Item, plan: SubtreePlan) -> SubtreePlan:
    """
    Pass a plan through unless it changes more than MAX_PLAN_ITEMS items.

    Checked when the plan is built, so a preview is refused before it issues
    a token and an apply before it writes.

    Args:
        - root (Item): the plan's root, for the message.
        - plan (SubtreePlan): the plan.

    Returns:
        - plan (SubtreePlan): the same plan.

    Raises:
        - PlanSizeError: the plan changes too many items.
    """
    if len(plan.changes) > MAX_PLAN_ITEMS:
        raise PlanSizeError(root.key, len(plan.changes), MAX_PLAN_ITEMS)
    return plan
