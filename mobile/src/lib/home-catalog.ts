/**
 * Selección editorial de Inicio (V6): grabaciones reales de MusicBrainz, comprobadas el 2026-10-20 contra
 * GET /v1/tracks/{mbid} (todas resuelven, con portada). Alimenta la portada, En el radar, Detrás del sonido y el
 * descubrimiento de Tu frecuencia cuando aún no hay Guardados.
 *
 * Para ampliarla: buscar la canción en TrackDNA, copiar el MBID canónico que devuelve la ficha y los datos tal como
 * los da la API (sello de la edición original, géneros de MusicBrainz y portada); nunca de memoria. Título y artista
 * se muestran mientras carga la ficha; el dato de En el radar y Detrás del sonido sale siempre de la ficha, no de aquí.
 * `connections`: la ficha documenta samples, remezclas, mashups o créditos de producción (candidata a Detrás del sonido).
 */
export type EditorialPick = {
  mbid: string;
  title: string;
  artist: string;
  /** Artista principal en MusicBrainz: para «más de este artista» sin comparar nombres. */
  artist_mbid: string;
  year: string | null;
  /** Sello de la edición original (null si MusicBrainz no lo documenta). */
  label: string | null;
  /** Géneros de MusicBrainz de la grabación o de su lanzamiento ([] si no constan). */
  genres: string[];
  cover: string | null;
  connections?: boolean;
  /** Qué es la grabación cuando el título no basta (p. ej. «Nuxx edit», versión oficial de Underworld). */
  version?: 'original' | 'version' | 'remix' | 'unofficial';
};

const caa = (release: string) => `https://coverartarchive.org/release/${release}/front-500`;

export const EDITORIAL_PICKS: EditorialPick[] = [
  { mbid: '6c7556af-3a52-4d43-8e7d-3bf63d0838fe', title: 'Strings of Life', artist: 'Rhythim Is Rhythim', artist_mbid: '159edf29-c4ae-49c7-b1e6-1f082c60d4e3',
    year: '1987', label: 'Transmat', genres: ['Techno', 'House'], cover: caa('8a55622c-6d54-45e6-95be-8d9fe50650dd') },
  { mbid: 'c4afe6fb-2ef0-4c34-b447-efc2009d6cdf', title: 'Shades of Jae', artist: 'Moodymann', artist_mbid: '17d69e72-9cf2-496f-aa64-ba238de2087e',
    year: '2004', label: 'Peacefrog Records', genres: ['Electrónica'], cover: caa('31b6c2c2-b42a-4415-b048-561f18908850') },
  { mbid: '820fb8cb-15d7-4704-b276-026c030a0b46', title: 'Rain', artist: 'Kerri Chandler', artist_mbid: 'b2233a1e-2b25-4660-a578-b2e2de990792',
    year: '1998', label: 'Nervous Old Skool', genres: [], cover: caa('d7b0c5b0-692e-44f1-96e1-ea85448faa56') },
  { mbid: '86ce9f29-a296-485e-9422-8edb50c52b98', title: 'XTC', artist: 'DJ Koze', artist_mbid: 'dd4458c8-6728-4a44-980c-48107fa72bb8',
    year: '2015', label: 'Pampa Records', genres: ['House', 'Techno'], cover: caa('bc4dcd52-cb68-43a6-acb2-07f15c6b5604'), connections: true },
  { mbid: 'dd4d51c7-8043-4f87-93ed-d2e620ffe334', title: 'Never Grow Old', artist: 'Floorplan', artist_mbid: '224d7fb5-1abc-4327-8657-ae1ddc94e1d6',
    year: '2013', label: 'M-Plant', genres: ['Techno'], cover: caa('b0a6694b-076f-4ab8-9007-f5020a902e8f') },
  { mbid: 'f07bf85d-fe4b-4532-8953-786aa77ea600', title: 'Good Life', artist: 'Inner City', artist_mbid: '65a8e571-8a08-433f-a5bf-ead38c269ea6',
    year: '1988', label: 'Virgin', genres: ['House', 'Pop', 'Eurodance'], cover: caa('faf572a8-bec6-4069-bc81-6a99698f5c84'), connections: true },
  { mbid: 'a15ea76e-9827-4108-bf5d-a44cf0dc4723', title: 'Born Slippy (Nuxx edit)', artist: 'Underworld', artist_mbid: 'ba2f4f3b-0293-4bc8-bb94-2f73b5207343',
    year: '1995', label: 'Smith Hyde Productions', genres: ['Techno', 'Progressive House', 'Trance'], cover: caa('8d068eac-c9bb-4017-8762-1175d2eec8f6'), version: 'version' },
  { mbid: '93a102e2-c8dc-43f4-8281-b621a7f5ac3c', title: 'Altered States', artist: 'Ron Trent', artist_mbid: '3af43a8a-f0b0-4dda-8cd8-ff4941c05316',
    year: '1992', label: 'Djax-Up-Beats', genres: ['House', 'Techno'], cover: caa('85a9de98-ebe4-4134-81ed-ccd8d4b5cfeb') },
  { mbid: '8edae321-48fc-4ae6-add1-bc976cb1a823', title: 'Lovelee Dae', artist: 'Blaze', artist_mbid: '65e331ed-ab1b-475a-81d1-4dad7e55043b',
    year: '1997', label: 'Urban Tracks', genres: ['House', 'Deep House'], cover: caa('2848ed85-6144-437c-9d0f-3d84b08c4dd4'), connections: true },
  { mbid: '98e34bc2-0e71-4205-8986-af891195ed4e', title: 'Hoodlum (original mix)', artist: 'Traumer', artist_mbid: '319c89bc-c7a3-4139-8386-a2a5b48b4ed7',
    year: '2014', label: 'Desolat', genres: ['House'], cover: caa('0392e2c9-0c5a-4b68-bf9d-46aee45af161') },
  { mbid: '9d619150-6b0f-4f14-b038-8503ae4c6c8f', title: 'Desire', artist: 'Chris Stassy', artist_mbid: '5b7f4511-1764-4d80-83b5-8c150f4636c5',
    year: '2024', label: null, genres: [], cover: caa('4df304a8-3f71-4c7b-b520-b1efc158a177') },
  { mbid: 'cdf0bea5-0e97-4f13-bd92-ccdfbf40f638', title: 'Can You Feel It', artist: 'Mr. Fingers', artist_mbid: '1e47567e-5192-43b9-af98-75e4998f9e52',
    year: '1986', label: 'Trax Records', genres: ['House'], cover: caa('46799fb1-1610-4666-9112-b8a673bc42b0'), connections: true },
  { mbid: '6e8b1a97-9b49-4898-9aa3-68db185b3653', title: 'Music Sounds Better With You (12” club mix)', artist: 'Stardust',
    artist_mbid: '7b75e88a-f211-4886-8c3d-dd9d7171eee5', year: '1998', label: 'Virgin', genres: ['House', 'Electro', 'French House'],
    cover: caa('135691ea-7b07-3f9c-9b57-506f47c7c1f1'), connections: true },
  { mbid: '32aff8b4-6d1f-4858-9ba4-82dfa2d4c7cd', title: 'Throw', artist: 'Paperclip People', artist_mbid: '2981acc0-69ab-4cb1-8233-e325b3309e9d',
    year: '1994', label: 'Virgin', genres: ['Techno', 'Ambient', 'House'], cover: caa('9cde7bb0-6ff7-4946-9612-3eca166f53ee') },
  { mbid: '7c4f24d0-d388-4dcb-ab77-446f28f7019b', title: "I Can't Kick This Feelin When It Hits", artist: 'Moodymann', artist_mbid: '17d69e72-9cf2-496f-aa64-ba238de2087e',
    year: '1996', label: 'KDJ', genres: ['House', 'Deep House'], cover: caa('22bc03cb-3709-42ce-8dcc-e6324745c42d'), connections: true },
  { mbid: 'd982f997-8be5-4401-9fb0-d58002b1f235', title: 'Promised Land', artist: 'Joe Smooth', artist_mbid: '348443bb-74fe-4459-8c19-3b72ad033d6c',
    year: '1988', label: 'Westside Records', genres: ['House', 'Deep House'], cover: caa('edb4fa89-8fa9-4b4f-962c-2c35c411ad1f') },
  { mbid: '06da69ce-40c6-4317-8ff3-527fee2d560e', title: 'Deep Burnt', artist: 'Pépé Bradock & the Grand brûlé’s choir', artist_mbid: '57f561e0-79e3-4bc2-99ce-6e313878c91b',
    year: '1999', label: 'Kif Records', genres: ['House', 'Deep House'], cover: caa('5d01e90e-9ac0-4912-a240-b0a4ca3e0f75'), connections: true },
];
