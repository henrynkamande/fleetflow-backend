from oauth.models import User

from . import conf


def allow_trial_without_payment() -> bool:
    if not conf.BILLING_ENFORCE:
        return True
    if conf.BILLING_ALLOW_TRIAL_WITHOUT_PAYMENT:
        return True
    if not conf.stripe_configured():
        return True
    return False


def owner_has_platform_access(owner: User | None) -> bool:
    if owner is None:
        return False
    if not conf.BILLING_ENFORCE or not conf.stripe_configured():
        return True
    return owner.billing_status in (
        User.BillingStatus.TRIALING,
        User.BillingStatus.ACTIVE,
    )


def owner_requires_checkout(owner: User | None) -> bool:
    if owner is None:
        return True
    if not conf.BILLING_ENFORCE or not conf.stripe_configured():
        return False
    return owner.billing_status in (
        User.BillingStatus.NOT_STARTED,
        User.BillingStatus.INCOMPLETE,
        User.BillingStatus.CANCELED,
        User.BillingStatus.PAST_DUE,
    )


company_has_platform_access = owner_has_platform_access
company_requires_checkout = owner_requires_checkout
