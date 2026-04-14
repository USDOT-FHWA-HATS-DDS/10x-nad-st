import click
from nad_ch.application.use_cases.data_producers import (
    add_data_producer,
    list_data_producers,
)
from nad_ch.application.use_cases.data_submissions import (
    get_data_submissions_by_producer,
    get_data_submission,
    retry_data_submission,
    reset_data_submission,
    cancel_data_submission,
    validate_data_submission,
)


@click.group()
@click.pass_context
def cli(ctx):
    pass


@cli.command()
@click.pass_context
@click.argument("producer_name")
def add_producer(ctx, producer_name):
    context = ctx.obj
    add_data_producer(context, producer_name)


@cli.command()
@click.pass_context
def list_producers(ctx):
    context = ctx.obj
    list_data_producers(context)


@cli.command()
@click.pass_context
@click.argument("producer")
def list_submissions_by_producer(ctx, producer):
    context = ctx.obj
    get_data_submissions_by_producer(context, producer)


@cli.command()
@click.pass_context
@click.argument("filename")
@click.argument("mapping_name")
def validate_submission(ctx, filename, mapping_name):
    context = ctx.obj
    validate_data_submission(context, filename, mapping_name)


@cli.command()
@click.pass_context
@click.argument("submission_id", type=int)
def retry_submission(ctx, submission_id):
    context = ctx.obj
    submission = retry_data_submission(context, submission_id)
    if submission:
        click.echo(
            f"Successfully retriggered submission {submission_id}. "
            f"Status: PENDING_VALIDATION"
        )
    else:
        click.echo(f"Failed to retry submission {submission_id}. Check logs for details.")


@cli.command()
@click.pass_context
@click.argument("submission_id", type=int)
def get_submission(ctx, submission_id):
    context = ctx.obj
    submission = get_data_submission(context, submission_id)
    if submission:
        click.echo(f"ID: {submission.id}")
        click.echo(f"Name: {submission.name}")
        click.echo(f"Status: {submission.status}")
        click.echo(f"File path: {submission.file_path}")
        click.echo(f"Producer: {submission.producer_name}")
    else:
        click.echo(f"Submission {submission_id} not found.")


@cli.command()
@click.pass_context
@click.argument("submission_id", type=int)
def reset_submission(ctx, submission_id):
    context = ctx.obj
    submission = reset_data_submission(context, submission_id)
    if submission:
        click.echo(
            f"Successfully reset submission {submission_id}. "
            f"Status: {submission.status}"
        )
    else:
        click.echo(f"Failed to reset submission {submission_id}. Check logs for details.")


@cli.command()
@click.pass_context
@click.argument("submission_id", type=int)
def cancel_submission(ctx, submission_id):
    context = ctx.obj
    submission = cancel_data_submission(context, submission_id)
    if submission:
        click.echo(
            f"Successfully canceled submission {submission_id}. "
            f"Status: {submission.status}"
        )
    else:
        click.echo(f"Failed to cancel submission {submission_id}. Check logs for details.")
