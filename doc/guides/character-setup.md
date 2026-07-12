# Setting up a character

> **New to PoseCap?** The [Getting Started guide](getting-started.md) walks the
> whole install-to-capture path in one go. This page is the focused reference for
> character setup — the skeleton options, and what to do when a character won't
> convert.

Live capture drives an **armature** (a character skeleton). PoseCap can drive
the built-in SMPL-X body, or any Mixamo or Unreal Engine character you bring in
— one click reorients and renames the skeleton so the pose stream fits it.

**What works:** any humanoid FBX with an armature and a bound mesh. Mixamo and
Unreal Engine skeletons are recognized automatically; anything else maps through a
small JSON file (below). This guide uses a free
[Mixamo](https://www.mixamo.com/) character as the example; an Unreal Engine /
Fortnite skeleton works the same way.

## Step 1 — Bring your character into Blender

Download a character from Mixamo as **FBX** (for example, *Y Bot*). In Blender:
**File → Import → FBX (.fbx)**, pick the file, and import.

Mixamo characters import lying on their side and very small (Y-up, 0.01 scale)
— that is normal and you do **not** need to fix it. PoseCap's convert step
handles the orientation for you.

## Step 2 — Pick it as the Target Armature

Open the **PoseCap** panel (3D Viewport → `N` → PoseCap tab). In
**Target Armature**, choose your character's armature (for a Mixamo import it is
named *Armature*).

The moment you set it, the Getting Started checklist ticks **Choose a target
character** green.

## Step 3 — Convert it for PoseCap

In the **Character Setup** section, leave **Skeleton** on **Auto-Detect** — it
recognizes Mixamo and Unreal Engine skeletons from their bone names — then click
**Convert Character for PoseCap**.

![The Character Setup section](images/character-setup-panel.png)

PoseCap renames the mapped bones to the SMPL-X convention, reorients them to the
capture frame, re-poses the arms to a T-pose where needed, and then
**self-verifies** the result. You will see a confirmation in the status bar:

> Character converted (Mixamo) — probe error 0.0000

The **probe error** is PoseCap checking its own work by driving a test motion
and measuring the result; lower is better and near zero is perfect. The whole
step is a single undoable action — **Ctrl+Z** reverts it.

Your character is now ready to be driven by [live capture](live-capture.md).

## Choosing the skeleton by hand

Auto-Detect covers Mixamo and Unreal out of the box. Use the **Skeleton**
dropdown when you want to be explicit or bring your own:

| Choice | Use it for |
|---|---|
| **Auto-Detect** | The default — recognizes the skeleton family from bone names |
| **Unreal Engine / Fortnite** | Unreal humanoid skeletons |
| **Mixamo** | Mixamo (`mixamorig:` bones) |
| **Custom Mapping** | Any other skeleton, via a JSON file mapping SMPL-X joints to your bone names |

## Troubleshooting

| Message | Meaning | Fix |
|---|---|---|
| "Could not recognize this skeleton" | Auto-Detect did not match a known family | Pick **Unreal Engine**, **Mixamo**, or **Custom Mapping** in the Skeleton dropdown |
| "the armature has a mirrored (negative) scale" | A negative-scaled import can't be reoriented | Select the armature, **Object → Apply → Rotation & Scale**, then convert again |
| "no mesh is bound to this armature" | The armature came in without its character mesh | Re-import so the mesh and its armature come together |
| "the armature is missing expected bones" | The skeleton isn't complete for the chosen preset | Check you picked the right preset, or use a Custom Mapping file |

---

*Next: [capture it live](live-capture.md). Full walk-through in the
[Getting Started guide](getting-started.md).*
