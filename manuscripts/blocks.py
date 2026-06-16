from django.utils.translation import gettext_lazy as _
from wagtail.blocks import ChoiceBlock, StreamBlock, StructBlock, TextBlock
from wagtail.images.blocks import ImageChooserBlock

from core.choices import LANGUAGE

from .choices import front_labels


class ParagraphWithLanguageBlock(StructBlock):
    label = ChoiceBlock(choices=front_labels, required=False, label=_("Label"))
    language = ChoiceBlock(choices=LANGUAGE, required=False, label=_("Language"))
    paragraph = TextBlock(required=False, label=_("Title"))

    class Meta:
        label = _("Paragraph with Language")


class ParagraphBlock(StructBlock):
    label = ChoiceBlock(choices=front_labels, required=False, label=_("Label"))
    paragraph = TextBlock(required=False, label=_("Paragraph"))

    class Meta:
        label = _("Paragraph")


class CompoundParagraphBlock(StructBlock):
    label = ChoiceBlock(choices=front_labels, required=False, label=_("Label"))
    eid = TextBlock(required=False, label=_("Equation id"))
    content = StreamBlock(
        [
            ("text", TextBlock(label=_("Text"))),
            ("formula", TextBlock(label=_("Formula"))),
        ],
        label=_("Content"),
        required=True,
    )

    class Meta:
        label = _("Compound paragraph")


class ImageBlock(StructBlock):
    label = ChoiceBlock(choices=front_labels, required=False, label=_("Label"))
    figid = TextBlock(required=False, label=_("Fig id"))
    figlabel = TextBlock(required=False, label=_("Fig label"))
    title = TextBlock(required=False, label=_("Title"))
    alttext = TextBlock(required=False, label=_("Alt text"))
    image = ImageChooserBlock(required=True)

    class Meta:
        label = _("Image")


class TableBlock(StructBlock):
    label = ChoiceBlock(choices=front_labels, required=False, label=_("Label"))
    tabid = TextBlock(required=False, label=_("Table id"))
    tablabel = TextBlock(required=False, label=_("Table label"))
    title = TextBlock(required=False, label=_("Title"))
    content = TextBlock(required=False, label=_("Content"))

    class Meta:
        label = _("Table")


class AuthorParagraphBlock(ParagraphBlock):
    surname = TextBlock(required=False, label=_("Surname"))
    given_names = TextBlock(required=False, label=_("Given names"))
    orcid = TextBlock(required=False, label=_("Orcid"))
    affid = TextBlock(required=False, label=_("Aff id"))
    char = TextBlock(required=False, label=_("Char link"))

    class Meta:
        label = _("Author Paragraph")


class AffParagraphBlock(ParagraphBlock):
    affid = TextBlock(required=False, label=_("Aff id"))
    text_aff = TextBlock(required=False, label=_("Full text Aff"))
    char = TextBlock(required=False, label=_("Char link"))
    orgname = TextBlock(required=False, label=_("Orgname"))
    orgdiv2 = TextBlock(required=False, label=_("Orgdiv2"))
    orgdiv1 = TextBlock(required=False, label=_("Orgdiv1"))
    zipcode = TextBlock(required=False, label=_("Zipcode"))
    city = TextBlock(required=False, label=_("City"))
    state = TextBlock(required=False, label=_("State"))
    country = TextBlock(required=False, label=_("Country"))
    code_country = TextBlock(required=False, label=_("Code country"))
    original = TextBlock(required=False, label=_("Original"))

    class Meta:
        label = _("Aff Paragraph")


class RefNameBlock(StructBlock):
    surname = TextBlock(required=False, label=_("Surname"))
    given_names = TextBlock(required=False, label=_("Given names"))


class RefParagraphBlock(ParagraphBlock):
    reftype = TextBlock(required=False, label=_("Ref type"))
    refid = TextBlock(required=False, label=_("Ref id"))
    authors = StreamBlock(
        [
            ("Author", RefNameBlock()),
        ],
        label=_("Authors"),
        required=False,
    )
    date = TextBlock(required=False, label=_("Date"))
    title = TextBlock(required=False, label=_("Title"))
    chapter = TextBlock(required=False, label=_("Chapter"))
    edition = TextBlock(required=False, label=_("Edition"))
    source = TextBlock(required=False, label=_("Source"))
    vol = TextBlock(required=False, label=_("Vol"))
    issue = TextBlock(required=False, label=_("Issue"))
    pages = TextBlock(required=False, label=_("Pages"))
    fpage = TextBlock(required=False, label=_("First page"))
    lpage = TextBlock(required=False, label=_("Last page"))
    doi = TextBlock(required=False, label=_("DOI"))
    access_id = TextBlock(required=False, label=_("Access id"))
    degree = TextBlock(required=False, label=_("Degree"))
    organization = TextBlock(required=False, label=_("Organization"))
    location = TextBlock(required=False, label=_("Location"))
    org_location = TextBlock(required=False, label=_("Org location"))
    num_pages = TextBlock(required=False, label=_("Num pages"))
    uri = TextBlock(required=False, label=_("Uri"))
    version = TextBlock(required=False, label=_("Version"))
    access_date = TextBlock(required=False, label=_("Access date"))

    class Meta:
        label = _("Ref Paragraph")
