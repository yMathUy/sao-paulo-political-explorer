from datetime import date

from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from .models import DeputyVote
from .services.chamber_api import (
    ChamberAPIError,
    get_deputy_by_id,
    get_deputy_expenses,
    get_deputy_propositions,
    get_sao_paulo_deputies,
    summarize_expenses,
)
from .services.senate_api import (
    SenateAPIError,
    get_current_sao_paulo_senators,
    get_senator_authorships,
    get_senator_by_id,
    get_senator_committees,
    get_senator_expenses,
    get_senator_mandates,
    get_senator_votes,
    summarize_senator_expenses,
)


def politicians_list(request):
    searched_name = request.GET.get("name", "").strip()
    selected_party = (
        request.GET.get("party", "")
        .strip()
        .upper()
    )

    error_message = None

    try:
        all_deputies = get_sao_paulo_deputies()

    except ChamberAPIError as error:
        all_deputies = []
        error_message = str(error)

    parties = sorted(
        {
            deputy.get("siglaPartido")
            for deputy in all_deputies
            if deputy.get("siglaPartido")
        }
    )

    filtered_deputies = all_deputies

    if searched_name:
        normalized_name = searched_name.casefold()

        filtered_deputies = [
            deputy
            for deputy in filtered_deputies
            if normalized_name
            in deputy.get("nome", "").casefold()
        ]

    if selected_party:
        filtered_deputies = [
            deputy
            for deputy in filtered_deputies
            if deputy.get(
                "siglaPartido",
                "",
            ).upper()
            == selected_party
        ]

    paginator = Paginator(filtered_deputies, 12)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "parties": parties,
        "searched_name": searched_name,
        "selected_party": selected_party,
        "results_count": len(filtered_deputies),
        "error_message": error_message,
    }

    return render(
        request,
        "politicians/politicians_list.html",
        context,
    )


def politician_detail(request, deputy_id):
    try:
        deputy = get_deputy_by_id(deputy_id)

    except ChamberAPIError as error:
        return render(
            request,
            "politicians/politician_detail.html",
            {"error_message": str(error)},
            status=503,
        )

    if not deputy:
        raise Http404("Politician not found.")

    current_year = date.today().year

    expense_error = None
    expense_summary = {
        "formatted_total": "Not available",
        "records_count": 0,
        "top_categories": [],
    }

    try:
        expenses = get_deputy_expenses(
            deputy_id=deputy_id,
            year=current_year,
        )

        expense_summary = summarize_expenses(expenses)

    except ChamberAPIError as error:
        expense_error = str(error)

    proposition_error = None
    propositions = []

    try:
        propositions = get_deputy_propositions(
            deputy_id=deputy_id,
            year=current_year,
        )

    except ChamberAPIError as error:
        proposition_error = str(error)

    recent_votes_query = (
        DeputyVote.objects
        .select_related("voting")
        .filter(
            deputy_id=deputy_id,
            voting__voting_date__year=current_year,
        )
        .order_by(
            "-voting__voting_date",
            "-vote_registered_at",
        )
    )

    votes_count = recent_votes_query.count()
    recent_votes = recent_votes_query[:8]

    context = {
        "deputy": deputy,
        "current_year": current_year,
        "expense_summary": expense_summary,
        "expense_error": expense_error,
        "propositions": propositions[:6],
        "propositions_count": len(propositions),
        "proposition_error": proposition_error,
        "votes_count": votes_count,
        "recent_votes": recent_votes,
    }

    return render(
        request,
        "politicians/politician_detail.html",
        context,
    )


def senators_list(request):
    error_message = None
    senators = []

    try:
        senators = get_current_sao_paulo_senators()

    except SenateAPIError as error:
        error_message = str(error)

    context = {
        "senators": senators,
        "results_count": len(senators),
        "error_message": error_message,
    }

    return render(
        request,
        "politicians/senators_list.html",
        context,
    )


def senator_detail(request, senator_id):
    try:
        senator = get_senator_by_id(senator_id)

    except SenateAPIError as error:
        return render(
            request,
            "politicians/senator_detail.html",
            {"error_message": str(error)},
            status=503,
        )

    if not senator:
        raise Http404("Senator not found.")

    mandates = []
    mandate_error = None

    try:
        mandates = get_senator_mandates(senator_id)

    except SenateAPIError as error:
        mandate_error = str(error)

    committees = []
    committee_error = None

    try:
        committees = get_senator_committees(senator_id)

    except SenateAPIError as error:
        committee_error = str(error)

    current_committees = [
        committee
        for committee in committees
        if committee["is_current"]
    ]

    authorships = []
    authorship_error = None
    current_year = date.today().year

    try:
        authorships = get_senator_authorships(senator_id)

    except SenateAPIError as error:
        authorship_error = str(error)

    current_authorships = [
        authorship
        for authorship in authorships
        if str(authorship["year"]) == str(current_year)
    ]
    primary_authorships_count = sum(
        authorship["is_primary_author"]
        for authorship in current_authorships
    )

    senate_votes = []
    senate_vote_error = None

    try:
        senate_votes = get_senator_votes(senator_id)

    except SenateAPIError as error:
        senate_vote_error = str(error)

    current_senate_votes = [
        vote
        for vote in senate_votes
        if str(vote["session_year"]) == str(current_year)
    ]

    senator_expense_error = None
    senator_expense_summary = {
        "formatted_total": "Not available",
        "records_count": 0,
        "top_categories": [],
    }

    try:
        senator_expenses = get_senator_expenses(
            senator_id,
            current_year,
        )
        senator_expense_summary = summarize_senator_expenses(
            senator_expenses
        )

    except SenateAPIError as error:
        senator_expense_error = str(error)

    context = {
        "senator": senator,
        "current_year": current_year,
        "mandates": mandates,
        "mandate_error": mandate_error,
        "current_committees": current_committees[:8],
        "current_committees_count": len(current_committees),
        "past_committees_count": (
            len(committees) - len(current_committees)
        ),
        "committee_error": committee_error,
        "authorships": current_authorships[:6],
        "authorships_count": len(current_authorships),
        "primary_authorships_count": primary_authorships_count,
        "coauthorships_count": (
            len(current_authorships) - primary_authorships_count
        ),
        "authorship_error": authorship_error,
        "senate_votes": current_senate_votes[:8],
        "senate_votes_count": len(current_senate_votes),
        "senate_vote_error": senate_vote_error,
        "senator_expense_summary": senator_expense_summary,
        "senator_expense_error": senator_expense_error,
    }

    return render(
        request,
        "politicians/senator_detail.html",
        context,
    )
