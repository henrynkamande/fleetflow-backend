from oauth.models import Company

from . import conf


def allow_trial_without_payment() -> bool:
    if not conf.BILLING_ENFORCE:
        return True
    if conf.BILLING_ALLOW_TRIAL_WITHOUT_PAYMENT:
        return True
    if not conf.stripe_configured():
        return True
    return False


def company_has_platform_access(company: Company | None) -> bool:
    if company is None:
        return False
    if not conf.BILLING_ENFORCE or not conf.stripe_configured():
        return True
    return company.billing_status in (
        Company.BillingStatus.TRIALING,
        Company.BillingStatus.ACTIVE,
    )


def company_requires_checkout(company: Company | None) -> bool:
    if company is None:
        return True
    if not conf.BILLING_ENFORCE or not conf.stripe_configured():
        return False
    return company.billing_status in (
        Company.BillingStatus.NOT_STARTED,
        Company.BillingStatus.INCOMPLETE,
        Company.BillingStatus.CANCELED,
        Company.BillingStatus.PAST_DUE,
    )
