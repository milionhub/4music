"""Relaciones musicales de MusicBrainz reutilizadas por el perfil de artista (colaboraciones / conexiones).

El motor de recomendación por créditos compartidos de T1 se sustituyó en T1.3 por app/recommend.py.
"""

# Relaciones artista-artista de MusicBrainz que expresan un vínculo musical. Las personales
# (married, sibling, parent, involved with…) no se usan como conexión.
MUSICAL_RELATIONS = {
    "member of band", "collaboration", "is person", "subgroup", "supporting musician",
    "vocal supporting musician", "instrumental supporting musician", "founder", "tribute",
}
