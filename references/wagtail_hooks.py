# Third-party imports
import hashlib

from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import CreateView, SnippetViewSet

# Local application imports
from ai.utils.normalizers import stz_norm
from config.menu import get_menu_order
from references.data_utils import get_reference
from references.models import Reference


class ReferenceCreateView(CreateView):
    def form_valid(self, form):
        # Obtener el contenido de mixed_citation del formulario
        mixed_citation_text = form.cleaned_data["mixed_citation"].strip()
        lineas = mixed_citation_text.split("\n")  # Dividir por saltos de línea

        # Crear un nuevo objeto Reference por cada línea válida
        for linea in lineas:
            linea = linea.strip()  # Eliminar espacios adicionales en cada línea
            if linea:  # Evitar procesar líneas vacías
                normalized = stz_norm(linea)
                checksum = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                new_reference, created = Reference.objects.get_or_create(
                    checksum=checksum,
                    defaults={
                        "mixed_citation": linea,
                        "normalized_citation": normalized,
                        "status": 1,
                        "creator": self.request.user,
                    },
                )
                if created:
                    get_reference.delay(new_reference.id)
                print(f"Creado Reference: {new_reference.mixed_citation}")

        # Redirigir después de la creación de los objetos
        return HttpResponseRedirect(self.get_success_url())


class ReferenceModelViewSet(SnippetViewSet):
    model = Reference
    add_view_class = ReferenceCreateView
    menu_name = "references"
    menu_label = _("References")
    menu_icon = "openquote"
    menu_order = get_menu_order("references")
    exclude_from_explorer = False
    list_per_page = 20
    add_to_admin_menu = True


register_snippet(ReferenceModelViewSet)
