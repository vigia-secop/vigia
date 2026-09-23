"""Pruebas del informe de calibración.

Lo que decide si una calibración vale no es la tasa: es saber **sobre cuánto**
se calculó. Una Regla que enciende en el 5 % suena tranquila hasta que uno se
entera de que no pudo mirar a la mitad de las entidades.

Por eso lo que se comprueba aquí es, sobre todo, que las tres cuentas se
mantengan separadas —encendió, no encendió, no se pudo mirar— y que la tercera
salga **antes** que el resultado en el informe. Si sale después, o no sale, el
número de arriba se lee como si cubriera todo.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vigia.reglas import fraccionamiento
from vigia.reglas.calibrar_fraccionamiento import informe, separar

AHORA = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _grupo(**cambios):
    base = {
        "nit_entidad": "890399011",
        "nombre_entidad": "ALCALDIA MUNICIPIO DE VIJES",
        "proveedor_tipo": "NIT", "proveedor_numero": "900629234",
        "mes": "2026-07-01", "contratos": 6,
        "suma": 290911738, "techo": 73526697,
        "p95_entidad": 68000000, "minimas_entidad": 41,
        "contratos_ids": ["CO1.PCCNTR.1", "CO1.PCCNTR.2"],
    }
    base.update(cambios)
    return base


def _datos(grupos):
    return {
        "recorte": {"minimas_medibles": 9423, "entidades": 1429,
                    "grupos": 8634, "desde": "2026-06-10",
                    "hasta": "2026-09-14"},
        "grupos": grupos,
    }


class TestLasTresCuentasNoSeMezclan:
    def test_los_ciegos_no_entran_al_denominador(self):
        # Si entraran, la tasa saldría más baja de lo que es y el informe
        # diría que la Regla enciende menos de lo que enciende.
        grupos = [
            _grupo(),
            _grupo(nit_entidad="999", techo=44118060000, p95_entidad=50000000),
            _grupo(nit_entidad="888", minimas_entidad=3),
        ]
        mirables, ciegos = separar(grupos, fraccionamiento.umbrales_iniciales())
        assert len(mirables) == 1
        assert len(ciegos) == 2

    def test_el_informe_dice_por_que_no_se_pudo_mirar_cada_uno(self):
        texto = informe(_datos([
            _grupo(),
            _grupo(nit_entidad="999", techo=44118060000, p95_entidad=50000000),
            _grupo(nit_entidad="888", minimas_entidad=3),
        ]), momento=AHORA)
        assert "techo no creíble" in texto
        assert "menos de 5 mínimas cuantías" in texto

    def test_dice_que_ciego_no_es_limpio(self):
        # La frase es el punto entero del bloque.
        texto = informe(_datos([
            _grupo(),
            _grupo(nit_entidad="999", techo=44118060000, p95_entidad=50000000),
        ]), momento=AHORA)
        assert "NO quiere decir que esas entidades esten limpias" in texto

    def test_la_cobertura_va_antes_que_el_resultado(self):
        texto = informe(_datos([_grupo()]), momento=AHORA)
        assert texto.index("LA COBERTURA") < texto.index("EL RESULTADO")


class TestElInformeNoConcluyeNada:
    def test_no_deja_la_regla_activa(self):
        texto = informe(_datos([_grupo()]), momento=AHORA)
        assert "sigue en «calibracion»" in texto
        assert "Activarla es un acto aparte" in texto

    def test_escribe_lo_que_la_bandera_no_dice(self):
        texto = informe(_datos([_grupo()]), momento=AHORA)
        assert "NO ES UNA PUBLICACION NI UNA ACUSACION" in texto
        assert "cabia en el tope" in texto
        assert "no quiere decir el mismo objeto" in texto

    def test_avisa_si_casi_todo_es_una_sola_entidad(self):
        # Una tasa global que en realidad describe a una entidad no describe
        # al país, y quien lea el número tiene que saberlo.
        grupos = [_grupo(nit_entidad="111", nombre_entidad="UNA SOLA",
                         proveedor_numero=str(i), mes=f"2026-0{i}-01")
                  for i in range(1, 5)]
        grupos.append(_grupo(nit_entidad="222", nombre_entidad="OTRA"))
        texto = informe(_datos(grupos), momento=AHORA)
        assert "mas de la mitad de las alertas son de UNA entidad" in texto


class TestCuandoNoHayNadaQueMirar:
    def test_sin_grupos_mirables_lo_dice_sin_inventar(self):
        # «No se le puso nada delante» no es «no encontró nada».
        texto = informe(_datos([
            _grupo(techo=44118060000, p95_entidad=50000000),
        ]), momento=AHORA)
        assert "no se le puso nada delante" in texto

    def test_sin_ningun_grupo_tampoco_revienta(self):
        texto = informe(_datos([]), momento=AHORA)
        assert "No quedo ni un grupo que evaluar" in texto


class TestLaMuestraSirveParaRevisar:
    def test_trae_los_contratos_para_poder_abrirlos(self):
        texto = informe(_datos([_grupo()]), momento=AHORA)
        assert "CO1.PCCNTR.1" in texto

    def test_trae_las_dos_cifras_y_cuantas_veces(self):
        texto = informe(_datos([_grupo()]), momento=AHORA)
        assert "$290.911.738" in texto
        assert "$73.526.697" in texto
        assert "x3.96" in texto

    def test_la_muestra_es_repetible(self):
        # Sale ordenada por identidad, no al azar: dos calibraciones sobre los
        # mismos datos tienen que enseñar lo mismo o la revisión no se puede
        # comparar con la anterior.
        grupos = [_grupo(proveedor_numero=str(i)) for i in range(1, 8)]
        uno = informe(_datos(grupos), momento=AHORA)
        otro = informe(_datos(list(reversed(grupos))), momento=AHORA)
        assert uno == otro
