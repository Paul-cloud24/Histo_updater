def _load_image(self):
        """Lädt das erste Bild aus dem Ordner, normalisiert auf uint8."""
        from analysis.brightfield_pipeline import (find_brightfield_image,
                                                    load_as_uint8_rgb)
        try:
            path       = find_brightfield_image(self.folder)
            rgb        = load_as_uint8_rgb(path)
            # Auf max. 1200 px skalieren für die Vorschau
            h, w       = rgb.shape[:2]
            max_dim    = 1200
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                pil   = Image.fromarray(rgb).resize(
                    (int(w * scale), int(h * scale)), Image.LANCZOS)
                rgb   = np.array(pil)
            self._rgb      = rgb
            self._img_name = os.path.basename(path)
        except Exception as e:
            self.preview_label.setText(f"Fehler: {e}")
            self._rgb = None