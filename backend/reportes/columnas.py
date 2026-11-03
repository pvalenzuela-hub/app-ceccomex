"""Filters and value lists of the result columns, applied in the server because a month has too many rows.

Each column says how to filter what the table shows: a list holds the selected values, a text holds a fragment.
"""

from django.db.models import Q, TextField, Value
from django.db.models.functions import Coalesce, Replace

from comercio.busqueda import normalizar


VALORES_LIMITE = 200
VALORES_LIMITE_MAXIMO = 500
# A computed column reads this many rows in Python at most, about the time of the totals of a full month.
COLUMNA_MAX_FILAS_CALCULADAS = 50_000


def _texto_celda(value):
    """A value as the table shows it: decimal comma and no trailing ".0"."""
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".").replace(".", ",")
    return normalizar(value)


def _resultado(valores, limite, requiere_busqueda=False):
    return {"valores": valores[:limite], "recortada": len(valores) > limite, "requiere_busqueda": requiere_busqueda}


class ColumnaTexto:
    """Text available in SQL; high-cardinality columns still work because the list is searched and limited."""

    def __init__(self, expression, lista=True):
        # Plain text: lookups on a bare JSON key treat the selected values as JSON in SQLite.
        self.expression = Coalesce(expression, Value(""), output_field=TextField())
        self.lista = lista

    def filtrar(self, qs, nombre, filtro):
        qs = qs.alias(**{nombre: self.expression})
        if isinstance(filtro, list):
            return qs.filter(**{f"{nombre}__in": filtro})
        return qs.filter(Q(**{f"{nombre}__icontains": filtro}) | Q(**{f"{nombre}__icontains": normalizar(filtro)}))

    def distintos(self, qs, buscar="", limite=None):
        rows = qs.order_by().select_related(None).annotate(_valor=self.expression).filter(_valor__isnull=False).exclude(_valor="")
        if buscar:
            rows = rows.filter(Q(_valor__icontains=buscar) | Q(_valor__icontains=normalizar(buscar)))
        rows = rows.values_list("_valor", flat=True).distinct().order_by("_valor")
        return list(rows if limite is None else rows[:limite])

    def valores(self, qs, buscar, limite):
        return _resultado(self.distintos(qs, buscar, limite + 1), limite)


class ColumnaNumero(ColumnaTexto):
    """Amounts and quantities: a text filter with decimal comma or point alike; ",07" has no leading zero in the DIN TXT."""

    def __init__(self, expression):
        super().__init__(expression, lista=False)

    def filtrar(self, qs, nombre, filtro):
        term = str(filtro).replace(",", ".")
        term = term[1:] if term.startswith("0.") else term
        return qs.alias(**{nombre: Replace(self.expression, Value(","), Value("."), output_field=TextField())}).filter(**{f"{nombre}__icontains": term})


class ColumnaEntero:
    """Year, month or day: "1" must find January, not also October to December."""

    lista = False

    def __init__(self, lookup):
        self.lookup = lookup

    def filtrar(self, qs, nombre, filtro):
        return qs.filter(**{self.lookup: int(filtro)}) if str(filtro).isdigit() else qs.none()


class ColumnaCatalogo:
    """Description of a code: the list shows descriptions and the filter turns them back into codes."""

    lista = True

    def __init__(self, codigo, glosas):
        self.codigo = ColumnaTexto(codigo)
        self.glosas = glosas

    def filtrar(self, qs, nombre, filtro):
        if isinstance(filtro, list):
            elegidas = set(filtro)
            codigos = [codigo for codigo, glosa in self.glosas() if glosa in elegidas]
        else:
            buscado = normalizar(filtro)
            codigos = [codigo for codigo, glosa in self.glosas() if buscado in normalizar(glosa)]
        return self.codigo.filtrar(qs, nombre, codigos)

    def valores(self, qs, buscar, limite):
        glosas = dict(self.glosas())
        buscado = normalizar(buscar)
        encontrados = {glosas[codigo] for codigo in self.codigo.distintos(qs) if codigo in glosas and buscado in normalizar(glosas[codigo])}
        return _resultado(sorted(encontrados), limite)


class ColumnaRelacion:
    """Values of another table of the same document, such as ships or package types."""

    lista = True

    def __init__(self, filas, campo, glosas=None):
        self.filas = filas
        self.campo = campo
        self.glosas = glosas

    def _texto(self, codigo, glosas):
        return glosas.get(codigo) or codigo

    def filtrar(self, qs, nombre, filtro):
        filas = self.filas
        if self.glosas is not None:
            glosas = dict(self.glosas())
            codigos = filas.order_by().values_list(self.campo, flat=True).distinct()
            if isinstance(filtro, list):
                elegidas = set(filtro)
                codigos = [codigo for codigo in codigos if self._texto(codigo, glosas) in elegidas]
            else:
                buscado = normalizar(filtro)
                codigos = [codigo for codigo in codigos if buscado in normalizar(self._texto(codigo, glosas))]
            filas = filas.filter(**{f"{self.campo}__in": codigos})
        elif isinstance(filtro, list):
            filas = filas.filter(**{f"{self.campo}__in": filtro})
        else:
            filas = filas.filter(**{f"{self.campo}__icontains": filtro})
        return qs.filter(numero_ident__in=filas.order_by().values("numero_ident"))

    def valores(self, qs, buscar, limite):
        filas = self.filas.order_by().filter(numero_ident__in=qs.order_by().select_related(None).values("numero_ident")).exclude(**{self.campo: ""})
        if self.glosas is None:
            if buscar:
                filas = filas.filter(**{f"{self.campo}__icontains": buscar})
            return _resultado(list(filas.values_list(self.campo, flat=True).distinct().order_by(self.campo)[:limite + 1]), limite)
        glosas = dict(self.glosas())
        buscado = normalizar(buscar)
        textos = {self._texto(codigo, glosas) for codigo in filas.values_list(self.campo, flat=True).distinct()}
        return _resultado(sorted(texto for texto in textos if buscado in normalizar(texto)), limite)


class ColumnaCalculada:
    """Column computed in Python from each row, read after SQL narrows the rows and up to a limit."""

    def __init__(self, valor, etiqueta, palabras_en_texto=False, lista=False):
        self.valor = valor
        self.etiqueta = etiqueta
        # Every word of the value is inside the trigram-indexed product text, so it narrows the rows first.
        self.palabras_en_texto = palabras_en_texto
        self.lista = lista

    def _con_palabras(self, qs, texto):
        for word in normalizar(texto).split():
            qs = qs.filter(texto_producto__contains=word)
        return qs

    def prefiltrar(self, qs, filtro):
        if not self.palabras_en_texto:
            return qs
        if not isinstance(filtro, list):
            return self._con_palabras(qs, filtro)
        alguna = Q()
        for value in filtro:
            todas = Q()
            for word in normalizar(value).split():
                todas &= Q(texto_producto__contains=word)
            alguna |= todas
        return qs.filter(alguna)

    def cumple(self, row, filtro):
        texto = _texto_celda(self.valor(row))
        if isinstance(filtro, list):
            return texto in {normalizar(value) for value in filtro}
        return normalizar(filtro) in texto

    def valores(self, qs, buscar, limite):
        filas = self._con_palabras(qs, buscar) if self.palabras_en_texto else qs
        if filas.count() > COLUMNA_MAX_FILAS_CALCULADAS:
            return _resultado([], limite, requiere_busqueda=True)
        buscado = normalizar(buscar)
        encontrados = set()
        for row in filas.order_by().select_related(None).iterator(chunk_size=2000):
            value = str(self.valor(row) or "")
            if value and buscado in normalizar(value):
                encontrados.add(value)
        return _resultado(sorted(encontrados), limite)


def aplicar_filtros_columnas(qs, filtros_columnas, fuente):
    """Rows where each column meets its filter. SQL first; computed columns are then read over what is left."""
    calculadas = []
    for position, (key, filtro) in enumerate(filtros_columnas.items()):
        columna = fuente(key)
        if isinstance(columna, ColumnaCalculada):
            qs = columna.prefiltrar(qs, filtro)
            calculadas.append((columna, filtro))
        else:
            qs = columna.filtrar(qs, f"_columna_{position}", filtro)
    if not calculadas:
        return qs
    if qs.count() > COLUMNA_MAX_FILAS_CALCULADAS:
        nombres = ", ".join(columna.etiqueta for columna, _ in calculadas)
        raise ValueError(f"Hay demasiados registros para filtrar por {nombres}. Acote el período o agregue otros filtros.")
    ids = [
        row.id for row in qs.order_by().select_related(None).iterator(chunk_size=2000)
        if all(columna.cumple(row, filtro) for columna, filtro in calculadas)
    ]
    return qs.filter(id__in=ids)
