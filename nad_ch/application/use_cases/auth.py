import re
from nad_ch.application.exceptions import (
    InvalidEmailDomainError,
    InvalidEmailError,
    OAuth2TokenError,
)
from nad_ch.application.interfaces import ApplicationContext
from nad_ch.core.entities import User, DataProducer


def get_or_create_user(ctx: ApplicationContext, provider_name: str, email: str) -> User:
    """
    Using an email address, retrieve the entity of the user who has just logged in. If
    no such user exists, create a new one and return it.
    """
    user = ctx.users.get_by_email(email)

    if user:
        if provider_name == "dev" and not user.is_active:
            _enrich_dev_user(ctx, user)
        return user

    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        error_message = "Invalid email address provided."
        ctx.logger.error(f"get_or_create_user error: {error_message}")
        raise InvalidEmailError(error_message)

    new_user = User(
        email=email,
        login_provider=provider_name,
        logout_url=ctx.auth.get_logout_url(provider_name),
    )
    saved_user = ctx.users.add(new_user)

    if provider_name == "dev":
        _enrich_dev_user(ctx, saved_user)

    return saved_user


def _enrich_dev_user(ctx: ApplicationContext, user: User) -> User:
    producer_name = "Dev Producer"
    producer = ctx.producers.get_by_name(producer_name)
    if not producer:
        producer = DataProducer(producer_name)
        producer = ctx.producers.add(producer)

    user.associate_with_data_producer(producer).activate()
    return ctx.users.update(user)


def get_logged_in_user_redirect_url(
    ctx: ApplicationContext,
    provider_name: str,
    state_token: str,
    acr_values: str = None,
    nonce: str = None,
) -> str | None:
    return ctx.auth.make_login_url(
        provider_name, state_token, acr_values=acr_values, nonce=nonce
    )


def get_logged_out_user_redirect_url(
    ctx: ApplicationContext, provider_name: str
) -> str | None:
    return ctx.auth.make_logout_url(provider_name)


def get_oauth2_token(
    ctx: ApplicationContext, provider_name: str, code: str
) -> str | None:
    oauth2_token = ctx.auth.fetch_oauth2_token(provider_name, code)

    if not oauth2_token:
        error_message = "Could not get access token."
        ctx.logger.error(f"OAUTH2 error: {error_message}")
        raise OAuth2TokenError(error_message)

    return oauth2_token


def get_user_email(
    ctx: ApplicationContext, provder_name: str, oath2_token: str
) -> str | None:
    return ctx.auth.fetch_user_email_from_login_provider(provder_name, oath2_token)


def get_user_email_domain_status(
    ctx: ApplicationContext, email: str | list[str]
) -> bool:
    is_valid_domain = ctx.auth.user_email_address_has_permitted_domain(email)

    if not is_valid_domain:
        error_message = "Attempted login with non-permitted email domain."
        ctx.logger.info(f"OAUTH2 error: {error_message}")
        raise InvalidEmailDomainError(error_message)

    return is_valid_domain
