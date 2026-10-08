from app.core.dedupe import JobRecord, canonical_url, find_duplicates, job_key


def test_job_key_ignores_case_punctuation_and_company_suffix() -> None:
    assert job_key("Mozn LLC", "Software Engineer", "Riyadh") == job_key(
        "mozn", "software engineer ", "riyadh"
    )


def test_canonical_url_drops_tracking_params() -> None:
    a = canonical_url("https://www.indeed.com/viewjob?jk=abc&utm_source=x&from=serp#top")
    assert a == canonical_url("http://indeed.com/viewjob/?jk=abc")


def test_find_duplicates_by_key_url_and_text() -> None:
    jd = "We are hiring a React developer in Riyadh with 3 years of experience. " * 5
    old = [
        JobRecord(
            id="1",
            company="Mozn",
            title="Software Engineer",
            city="Riyadh",
            jd_text="x",
            status="applied",
        ),
        JobRecord(
            id="2",
            company="Other",
            title="Dev",
            url="https://bayt.com/job/9?utm_medium=e",
            jd_text="y",
        ),
        JobRecord(id="3", company="Third", title="Dev", jd_text=jd + " Apply now."),
        JobRecord(id="4", company="Unrelated", title="Teacher", jd_text="Teach maths to grade 9."),
    ]
    new = JobRecord(
        id="new",
        company="MOZN",
        title="Software engineer",
        city="riyadh",
        url="https://bayt.com/job/9",
        jd_text=jd,
    )
    matches = {m.job_id: m for m in find_duplicates(new, old)}
    assert set(matches) == {"1", "2", "3"}
    assert matches["1"].status == "applied"
    assert "same job URL" in matches["2"].reasons
    assert matches["3"].similarity >= 90
