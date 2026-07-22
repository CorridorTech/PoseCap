"""Native Linux installer for PoseCap (ADR-0011).

Mirrors packaging/installer/*.ps1's behavior and JSON contracts (installed
component inventory, Pose Backend manifests) so the two platforms share the
same product state shape even though each ships its own native packaging
surface. Covers Base, MediaPipe Lite (CPU), and PEAR (NVIDIA/CUDA).
"""
